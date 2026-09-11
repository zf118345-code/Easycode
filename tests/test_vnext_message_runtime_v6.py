from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.message_runtime_v6 import MessageRuntimeError, MessageRuntimeV6
from core.vnext.player_bundle import VNextPlayerBundleManager
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    DurationValue,
    EntityReferenceValue,
    JsonValue,
    ListValue,
    ProgramDocument,
    ProgramFunction,
    ResultBinding,
    StringValue,
)
from core.vnext.program_validation import types_compatible
from core.vnext.runtime import VNextRuntime, vnext_runtime


def _service(tmp_path: Path) -> MessageRuntimeV6:
    return MessageRuntimeV6(tmp_path / "runtime" / "messages.sqlite3")


def _identity(
    service: MessageRuntimeV6,
    project: str,
    name: str,
    key: str,
) -> tuple[dict, dict]:
    instance = service.register_instance(project, name, endpoint_key=key)
    context = service.instance_context(project, instance_id=instance["instance_id"])
    return instance, context


def test_message_value_static_type_accepts_only_by_value_structures():
    assert types_compatible("json_value", "message_value")
    assert types_compatible("list<map<string,string>>", "message_value")
    assert types_compatible("map<string,list<int64>>", "message_value")
    assert not types_compatible("window_ref", "message_value")
    assert not types_compatible("map<int64,string>", "message_value")


def test_all_visible_message_contracts_are_runtime_verified_and_read_mode_is_typed():
    function_ids = (
        "official.message.send",
        "official.message.wait_receive",
        "official.message.wait_read",
        "official.message.cancel",
    )
    contracts = [official_function_registry_v6.require(item) for item in function_ids]
    assert all(
        contract.verified_platforms == ("windows", "android_adb", "no_target")
        for contract in contracts
    )
    wait_read = official_function_registry_v6.require("official.message.wait_read")
    mode = next(parameter for parameter in wait_read.parameters if parameter.name == "mode")
    assert mode.value_type == "enum<read_wait_mode>"
    assert mode.default == "all"
    assert mode.constraints["choices"] == [
        {"label": "全部", "value": "all"},
        {"label": "任一", "value": "any"},
    ]


def test_instance_identity_is_stable_unique_and_rename_preserves_pending_route(tmp_path: Path):
    service = _service(tmp_path)
    sender, sender_context = _identity(service, "project-a", "主实例", "sender")
    recipient, recipient_context = _identity(
        service, "project-a", "接收实例", "recipient"
    )

    same_host = MessageRuntimeV6(service.database_path).host_id()
    assert same_host == sender["host_id"] == recipient["host_id"]
    assert EntityReferenceValue(
        value_id="value_instance",
        **recipient["reference"],
    ).reference_id == recipient["reference"]["reference_id"]
    with pytest.raises(MessageRuntimeError, match="同名") as duplicate:
        service.register_instance("project-a", "接收实例", endpoint_key="other")
    assert duplicate.value.error_id == "message.instance_conflict"

    batch = service.send(
        sender_context,
        [recipient["reference"]],
        "邀请",
        {"房间码": "0012"},
        30_000,
    )
    renamed = service.rename_instance("project-a", recipient["instance_id"], "接收实例-新名")

    assert renamed["instance_id"] == recipient["instance_id"]
    assert batch["recipients"][0]["recipient_display_name"] == "接收实例"
    assert batch["recipients"][0]["recipient"]["reference_id"] == renamed["reference"]["reference_id"]
    assert service.wait_receive(
        recipient_context,
        "邀请",
        sender["reference"],
        0,
    )["content"] == {"房间码": "0012"}


def test_multi_recipient_send_is_atomic_and_rejects_unknown_or_duplicate(tmp_path: Path):
    service = _service(tmp_path)
    _sender, sender_context = _identity(service, "project-a", "A", "a")
    b, _ = _identity(service, "project-a", "B", "b")
    c, _ = _identity(service, "project-a", "C", "c")
    unknown = dict(c["reference"], instance_id="instance_unknown")
    unknown["reference_id"] = "instance_ref.v1.invalid.invalid"

    with pytest.raises(MessageRuntimeError) as error:
        service.send(sender_context, [b["reference"], unknown], "通知", {"值": 1})
    assert error.value.error_id == "message.instance_unknown"
    assert service.diagnostic_snapshot("project-a")["messages"] == []

    with pytest.raises(MessageRuntimeError, match="重复"):
        service.send(sender_context, [b["reference"], b["reference"]], "通知", None)
    assert service.diagnostic_snapshot("project-a")["messages"] == []

    batch = service.send(sender_context, [b["reference"], c["reference"]], "通知", [1, 2])
    assert [item["status"] for item in batch["recipients"]] == ["waiting_read", "waiting_read"]
    assert len({item["message_id"] for item in batch["recipients"]}) == 2


def test_content_is_copied_by_value_and_invalid_content_creates_no_batch(tmp_path: Path):
    service = _service(tmp_path)
    a, a_context = _identity(service, "project-a", "A", "a")
    b, b_context = _identity(service, "project-a", "B", "b")
    content = {"队伍": ["甲", {"编号": "001"}]}

    service.send(a_context, [b["reference"]], "队伍", content)
    content["队伍"][1]["编号"] = "changed"
    received = service.wait_receive(b_context, "队伍", a["reference"], 0)
    assert received is not None
    assert received["content"] == {"队伍": ["甲", {"编号": "001"}]}
    received["content"]["队伍"][1]["编号"] = "receiver-change"

    with pytest.raises(MessageRuntimeError) as non_finite:
        service.send(a_context, [b["reference"]], "非法", {"value": float("nan")})
    assert non_finite.value.error_id == "message.content_invalid"
    with pytest.raises(MessageRuntimeError):
        service.send(a_context, [b["reference"]], "非法", {1: "not-a-string-key"})
    with pytest.raises(MessageRuntimeError):
        service.send(a_context, [b["reference"]], "非法", object())
    assert len(service.diagnostic_snapshot("project-a")["messages"]) == 1


def test_wait_receive_acks_only_after_decode_and_ttl_expires(tmp_path: Path):
    service = _service(tmp_path)
    a, a_context = _identity(service, "project-a", "A", "a")
    b, b_context = _identity(service, "project-a", "B", "b")
    batch = service.send(a_context, [b["reference"]], "短消息", "value", 1)
    time.sleep(0.01)

    assert service.wait_receive(b_context, "短消息", a["reference"], 0) is None
    status = service.wait_read(a_context, batch, "all", 0)
    assert status["condition_met"] is False
    assert status["unread_instances"] == []
    assert [item["reference_id"] for item in status["expired_instances"]] == [
        b["reference"]["reference_id"]
    ]


def test_wait_read_all_any_timeout_and_partial_cancel_are_independent(tmp_path: Path):
    service = _service(tmp_path)
    a, a_context = _identity(service, "project-a", "A", "a")
    b, b_context = _identity(service, "project-a", "B", "b")
    c, c_context = _identity(service, "project-a", "C", "c")
    batch = service.send(a_context, [b["reference"], c["reference"]], "房间码", "215")

    assert service.wait_read(a_context, batch, "all", 0)["condition_met"] is False
    assert service.wait_receive(b_context, "房间码", a["reference"], 0)
    any_result = service.wait_read(a_context, batch, "any", 0)
    assert any_result["condition_met"] is True
    assert [item["reference_id"] for item in any_result["unread_instances"]] == [
        c["reference"]["reference_id"]
    ]
    assert service.wait_read(a_context, batch, "all", 0)["condition_met"] is False

    cancelled = service.cancel(a_context, batch, c["reference"])
    assert [item["reference_id"] for item in cancelled["cancelled_instances"]] == [
        c["reference"]["reference_id"]
    ]
    assert cancelled["not_cancelled_instances"] == []
    assert service.wait_receive(c_context, "房间码", a["reference"], 0) is None
    not_cancelled = service.cancel(a_context, batch, b["reference"])["not_cancelled_instances"]
    assert [item["reference_id"] for item in not_cancelled] == [
        b["reference"]["reference_id"]
    ]


def test_project_isolation_and_stable_duplicate_batch_idempotency(tmp_path: Path):
    service = _service(tmp_path)
    a1, a1_context = _identity(service, "project-a", "A", "project-a-a")
    b1, b1_context = _identity(service, "project-a", "B", "project-a-b")
    b2, b2_context = _identity(service, "project-b", "B", "project-b-b")

    with pytest.raises(MessageRuntimeError):
        service.send(a1_context, [b2["reference"]], "隔离", "secret")

    first = service.send(
        a1_context,
        [b1["reference"]],
        "幂等",
        {"值": 1},
        batch_id="batch_stable_request",
    )
    repeated = service.send(
        a1_context,
        [b1["reference"]],
        "幂等",
        {"值": 1},
        batch_id="batch_stable_request",
    )
    assert repeated == first
    with pytest.raises(MessageRuntimeError) as conflict:
        service.send(
            a1_context,
            [b1["reference"]],
            "幂等",
            {"值": 2},
            batch_id="batch_stable_request",
        )
    assert conflict.value.error_id == "message.idempotency_conflict"
    assert service.wait_receive(b2_context, "幂等", None, 0) is None
    assert service.wait_receive(b1_context, "幂等", a1["reference"], 0)


def test_diagnostics_are_redacted(tmp_path: Path):
    service = _service(tmp_path)
    _a, a_context = _identity(service, "project-a", "敏感发送者", "a")
    b, _ = _identity(service, "project-a", "敏感接收者", "b")
    service.send(a_context, [b["reference"]], "秘密名称", {"token": "top-secret"})

    diagnostics = service.diagnostic_snapshot("project-a")
    encoded = str(diagnostics)
    assert "秘密名称" not in encoded
    assert "top-secret" not in encoded
    assert "敏感发送者" not in encoded
    assert "敏感接收者" not in encoded
    assert diagnostics["messages"][0]["status"] == "waiting_read"


def _ecir(instruction: dict, *, project_path: str) -> dict:
    return {
        "program_model_version": 1,
        "project_path": project_path,
        "target_platform": "no_target",
        "supported_platforms": ["no_target"],
        "entry_function_id": "function_main",
        "project_variables": [],
        "functions": [{
            "function_id": "function_main",
            "name": "主程序",
            "parameters": [],
            "parameter_definitions": [],
            "return_type": "unit",
            "instructions": [instruction],
        }],
    }


def _wait_terminal(runtime: VNextRuntime, execution_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    snapshot = runtime.snapshot(execution_id)
    while snapshot["status"] not in {"completed", "failed", "cancelled"}:
        if time.monotonic() >= deadline:
            raise AssertionError(f"runtime did not finish: {snapshot}")
        time.sleep(0.05)
        snapshot = runtime.snapshot(execution_id)
    return snapshot


def test_isolated_workers_share_the_same_sqlite_queue(tmp_path: Path):
    service = _service(tmp_path)
    a, a_context = _identity(service, "project-a", "A", "a")
    b, b_context = _identity(service, "project-a", "B", "b")
    runtime = VNextRuntime(use_worker_process=True, persist_event_log=False)
    try:
        send_instruction = {
            "instruction_id": "statement_send",
            "opcode": "message.send",
            "function_id": "official.message.send",
            "arguments": {
                "official.message.send.parameter.recipients": [b["reference"]],
                "official.message.send.parameter.name": "跨进程",
                "official.message.send.parameter.content": {"kind": "json", "value": {"code": "007"}},
                "official.message.send.parameter.ttl": {"kind": "duration", "milliseconds": 30_000},
            },
            "result_slot": "batch",
        }
        sent = runtime.start(
            _ecir(send_instruction, project_path=str(tmp_path)),
            execution_id="execution_message_sender",
            message_context=a_context,
        )
        sent = _wait_terminal(runtime, sent["execution_id"])
        assert sent["status"] == "completed", sent
        assert sent["variables"]["batch"]["recipients"][0]["status"] == "waiting_read"

        receive_instruction = {
            "instruction_id": "statement_receive",
            "opcode": "message.wait_receive",
            "function_id": "official.message.wait_receive",
            "arguments": {
                "official.message.wait_receive.parameter.name": "跨进程",
                "official.message.wait_receive.parameter.sender": a["reference"],
                "official.message.wait_receive.parameter.timeout": {"kind": "duration", "milliseconds": 1_000},
            },
            "result_slot": "received",
        }
        received = runtime.start(
            _ecir(receive_instruction, project_path=str(tmp_path)),
            execution_id="execution_message_receiver",
            message_context=b_context,
        )
        received = _wait_terminal(runtime, received["execution_id"])
        assert received["status"] == "completed", received
        assert received["variables"]["received"]["content"] == {"code": "007"}
    finally:
        runtime.shutdown()


def test_program_document_compiles_to_ecir_and_crosses_isolated_worker_boundary(
    tmp_path: Path,
):
    """Exercise the real authoring model instead of hand-written ECIR fixtures."""

    service = _service(tmp_path)
    sender, sender_context = _identity(service, "project-a", "发送实例", "sender")
    recipient, recipient_context = _identity(
        service,
        "project-a",
        "接收实例",
        "recipient",
    )
    recipient_reference = EntityReferenceValue(
        value_id="value_recipient_reference",
        **recipient["reference"],
    )
    sender_reference = EntityReferenceValue(
        value_id="value_sender_reference",
        **sender["reference"],
    )
    sender_document = ProgramDocument(
        document_id="document_message_sender",
        function=ProgramFunction(
            function_id="project.message_sender",
            display_name="发送消息",
            statements=(
                CallStatement(
                    statement_id="statement_message_send",
                    function_id="official.message.send",
                    arguments={
                        "official.message.send.parameter.recipients": ListValue(
                            value_id="value_message_recipients",
                            item_type="instance_ref",
                            items=(recipient_reference,),
                        ),
                        "official.message.send.parameter.name": StringValue(
                            value_id="value_message_name",
                            value="编译链路",
                        ),
                        "official.message.send.parameter.content": JsonValue(
                            value_id="value_message_content",
                            payload={"room_code": "008", "round": 1},
                        ),
                        "official.message.send.parameter.ttl": DurationValue(
                            value_id="value_message_ttl",
                            milliseconds=30_000,
                        ),
                    },
                    result_binding=ResultBinding(
                        symbol_id="symbol_message_batch",
                        display_name="发送批次",
                        value_type="message_batch",
                    ),
                ),
            ),
        ),
    )
    receiver_document = ProgramDocument(
        document_id="document_message_receiver",
        function=ProgramFunction(
            function_id="project.message_receiver",
            display_name="接收消息",
            statements=(
                CallStatement(
                    statement_id="statement_message_receive",
                    function_id="official.message.wait_receive",
                    arguments={
                        "official.message.wait_receive.parameter.name": StringValue(
                            value_id="value_receive_name",
                            value="编译链路",
                        ),
                        "official.message.wait_receive.parameter.sender": sender_reference,
                        "official.message.wait_receive.parameter.timeout": DurationValue(
                            value_id="value_receive_timeout",
                            milliseconds=1_000,
                        ),
                    },
                    result_binding=ResultBinding(
                        symbol_id="symbol_received_message",
                        display_name="收到的消息",
                        value_type="optional<received_message>",
                    ),
                ),
            ),
        ),
    )

    sender_compiled = compile_program_document(
        sender_document,
        official_function_registry_v6,
        target_platform="no_target",
    )
    receiver_compiled = compile_program_document(
        receiver_document,
        official_function_registry_v6,
        target_platform="no_target",
    )
    assert sender_compiled["valid"] is True, sender_compiled["diagnostics"]
    assert receiver_compiled["valid"] is True, receiver_compiled["diagnostics"]
    sender_plan = adapt_program_ecir_for_runtime(
        sender_compiled["ecir"],
        project_path=str(tmp_path),
    )
    receiver_plan = adapt_program_ecir_for_runtime(
        receiver_compiled["ecir"],
        project_path=str(tmp_path),
    )
    assert sender_plan["functions"][0]["instructions"][0]["opcode"] == "message.send"
    assert (
        receiver_plan["functions"][0]["instructions"][0]["opcode"]
        == "message.wait_receive"
    )

    runtime = VNextRuntime(use_worker_process=True, persist_event_log=False)
    try:
        sent = runtime.start(
            sender_plan,
            execution_id="execution_compiled_message_sender",
            message_context=sender_context,
        )
        sent = _wait_terminal(runtime, sent["execution_id"])
        assert sent["status"] == "completed", sent
        assert sent["variables"]["symbol_message_batch"]["recipients"][0][
            "status"
        ] == "waiting_read"

        received = runtime.start(
            receiver_plan,
            execution_id="execution_compiled_message_receiver",
            message_context=recipient_context,
        )
        received = _wait_terminal(runtime, received["execution_id"])
        assert received["status"] == "completed", received
        assert received["variables"]["symbol_received_message"]["content"] == {
            "room_code": "008",
            "round": 1,
        }
    finally:
        runtime.shutdown()


def test_decode_failure_never_marks_message_read(tmp_path: Path):
    service = _service(tmp_path)
    a, a_context = _identity(service, "project-a", "A", "a")
    b, b_context = _identity(service, "project-a", "B", "b")
    batch = service.send(a_context, [b["reference"]], "损坏", {"value": 1})
    with sqlite3.connect(service.database_path) as connection:
        connection.execute(
            "UPDATE message_batches SET content_json='not-json' WHERE batch_id=?",
            (batch["batch_id"],),
        )
    with pytest.raises(MessageRuntimeError) as error:
        service.wait_receive(b_context, "损坏", a["reference"], 0)
    assert error.value.error_id == "message.decode_failed"
    assert service.wait_read(a_context, batch, "all", 0)["unread_instances"]


def test_message_instance_http_api_uses_workspace_project_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EASYCODE_VNEXT_RUNTIME_DATA_DIR", str(tmp_path / "runtime-data"))
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    opened = client.post(
        "/api/vnext/workspaces/open",
        json={
            "path": str(tmp_path / "project"),
            "initialize": True,
            "project_name": "消息 API",
        },
    )
    assert opened.status_code == 200, opened.text
    workspace = opened.json()["workspace"]
    headers = {
        "X-Workspace-ID": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }
    created = client.post(
        "/api/vnext/message-instances",
        headers=headers,
        json={
            "display_name": "调试实例",
            "endpoint_key": "debug-slot-1",
            "endpoint_kind": "ide_debug",
        },
    )
    assert created.status_code == 200, created.text
    instance = created.json()
    assert instance["reference"]["reference_type"] == "instance_ref"

    renamed = client.patch(
        f"/api/vnext/message-instances/{instance['instance_id']}",
        headers=headers,
        json={"display_name": "调试实例-新名"},
    )
    assert renamed.status_code == 200, renamed.text
    listed = client.get("/api/vnext/message-instances", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["instances"][0]["display_name"] == "调试实例-新名"
    assert listed.json()["project_namespace"] == opened.json()["inspection"]["project_id"]


def test_player_runtime_uses_the_same_local_message_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    runtime_data = tmp_path / "shared-runtime"
    player_data = tmp_path / "player-data"
    monkeypatch.setenv("EASYCODE_VNEXT_RUNTIME_DATA_DIR", str(runtime_data))
    monkeypatch.setenv("EASYCODE_PLAYER_DATA_DIR", str(player_data))
    monkeypatch.setenv("EASYCODE_PLAYER_INSTANCE_KEY", "player-test-slot")
    monkeypatch.setenv("EASYCODE_PLAYER_INSTANCE_NAME", "Player测试实例")
    service = MessageRuntimeV6()
    signing_key_id = "test-player-signing-key"
    trust_domain = "product_" + hashlib.sha256(
        f"project-player-message\0{signing_key_id}".encode("utf-8")
    ).hexdigest()[:32]
    recipient = service.register_instance(
        "project-player-message",
        "接收实例",
        endpoint_key="receiver",
        trust_domain=trust_domain,
    )
    recipient_context = service.instance_context(
        "project-player-message",
        instance_id=recipient["instance_id"],
    )
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(tmp_path / "player-runtime")
    Path(manager._runtime_root).mkdir(parents=True)
    manager._manifest = {
        "project_id": "project-player-message",
        "name": "消息 Player",
    }
    manager._signature = {"key_id": signing_key_id}
    manager._project = {"targets": [], "default_target_id": None}
    manager._form = {"schema_version": 3, "title": "消息 Player", "pages": []}
    manager._ecir = _ecir({
        "instruction_id": "statement_player_send",
        "opcode": "message.send",
        "function_id": "official.message.send",
        "arguments": {
            "official.message.send.parameter.recipients": [recipient["reference"]],
            "official.message.send.parameter.name": "Player消息",
            "official.message.send.parameter.content": "来自独立Player",
            "official.message.send.parameter.ttl": {
                "kind": "duration",
                "milliseconds": 30_000,
            },
        },
        "result_slot": "batch",
    }, project_path=manager._runtime_root)
    try:
        started = manager.start({})
        finished = _wait_terminal(vnext_runtime, started["execution_id"])
        assert finished["status"] == "completed", finished
        received = service.wait_receive(recipient_context, "Player消息", None, 0)
        assert received is not None
        assert received["content"] == "来自独立Player"
        assert received["sender_display_name"] == "Player测试实例"
    finally:
        manager.shutdown()
