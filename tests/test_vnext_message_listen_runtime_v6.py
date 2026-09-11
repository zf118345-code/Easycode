from __future__ import annotations

import json
import sqlite3
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.message_runtime_v6 import (
    MessageRuntimeError,
    MessageRuntimeV6,
    program_uses_messages,
)
from core.vnext.program_compiler import compile_program_bundle
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
)
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    EntityReferenceValue,
    ListenStatement,
    LoopBinding,
    MessageEventSource,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.runtime import VNextRuntime


def _instruction(
    instruction_id: str,
    opcode: str,
    arguments: dict[str, Any],
    *,
    result_slot: str | None = None,
) -> dict[str, Any]:
    return {
        "instruction_id": instruction_id,
        "opcode": opcode,
        "arguments": arguments,
        "result_slot": result_slot,
        "source": {
            "document_id": "document_main",
            "function_id": "function.main",
            "statement_id": instruction_id,
        },
        "capabilities": [],
    }


def _log(instruction_id: str, content: Any) -> dict[str, Any]:
    return _instruction(
        instruction_id,
        "log.write",
        {
            "official.log.output.parameter.content": content,
            "official.log.output.parameter.level": "info",
            "official.log.output.parameter.category": "test",
        },
    )


def _reference(symbol_id: str, *, scope: str = "local") -> dict[str, Any]:
    key = "variable_id" if scope == "project" else "symbol_id"
    return {"kind": "reference", "scope": scope, key: symbol_id}


def _listener(
    sender: dict[str, Any] | None = None,
    *,
    condition: Any = None,
    handler_function_id: str = "function.handler",
    handler_arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _instruction(
        "listener.invite",
        "control.listen",
        {
            "event_source": {
                "kind": "message",
                "name": "invite",
                "sender": sender,
            },
            "receive_slot": "received",
            "condition": condition,
            "handler_function_id": handler_function_id,
            "handler_arguments": handler_arguments or {
                "handler.message": _reference("received"),
            },
            "dispatch": {
                "serial": True,
                "fifo": True,
                "safe_checkpoint": True,
            },
        },
    )


def _ecir(
    main: list[dict[str, Any]],
    handler: list[dict[str, Any]] | None = None,
    *,
    project_path: str = "",
    project_variables: list[dict[str, Any]] | None = None,
    targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    handler_parameters = [] if handler is None else [{
        "parameter_id": "handler.message",
        "name": "message",
        "display_name": "消息",
        "value_type": "received_message",
        "required": True,
        "default": None,
    }]
    functions = [{
        "function_id": "function.main",
        "name": "主程序",
        "parameters": [],
        "parameter_definitions": [],
        "return_type": "null",
        "instructions": main,
    }]
    if handler is not None:
        functions.append({
            "function_id": "function.handler",
            "name": "处理消息",
            "parameters": ["message"],
            "parameter_definitions": handler_parameters,
            "return_type": "null",
            "instructions": handler,
        })
    return {
        "ecir_version": 1,
        "program_model_version": 1,
        "entry_function_id": "function.main",
        "project_path": project_path,
        "project_variables": project_variables or [],
        "functions": functions,
        "targets": targets or [],
        "required_capabilities": ["messaging"],
        "supported_platforms": ["no_target", "windows", "android_adb"],
    }


def _service_world(
    tmp_path: Path,
) -> tuple[MessageRuntimeV6, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    service = MessageRuntimeV6(tmp_path / "runtime" / "messages.sqlite3")
    sender = service.register_instance("project-listen", "发送端", endpoint_key="sender")
    recipient = service.register_instance(
        "project-listen", "接收端", endpoint_key="recipient",
    )
    sender_context = service.instance_context(
        "project-listen", instance_id=sender["instance_id"],
    )
    recipient_context = service.instance_context(
        "project-listen", instance_id=recipient["instance_id"],
    )
    return service, sender, sender_context, recipient, recipient_context


def _send(
    service: MessageRuntimeV6,
    sender_context: dict[str, Any],
    recipient: dict[str, Any],
    content: Any,
) -> dict[str, Any]:
    return service.send(
        sender_context,
        [recipient["reference"]],
        "invite",
        content,
        30_000,
    )


def _terminal(
    runtime: VNextRuntime,
    execution_id: str,
    *,
    timeout: float = 8.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot["status"] in {"completed", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("监听运行未在限时内结束")


def _wait_for(
    predicate,
    *,
    timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待监听运行状态超时")


def _messages(snapshot: dict[str, Any]) -> list[str]:
    return [str(item["message"]) for item in snapshot["events"]]


def test_private_peek_and_atomic_claim_ack_only_after_successful_decode(
    tmp_path: Path,
) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"secret": "body"})
    message_id = batch["recipients"][0]["message_id"]

    candidates = service._peek_receive_candidates(
        recipient_context, "invite", sender["reference"],
    )
    assert [item["message_id"] for item in candidates] == [message_id]
    assert service.wait_read(sender_context, batch, "all", 0)["unread_instances"]
    assert service._claim_receive_candidate(
        recipient_context,
        message_id,
        expected_name="other",
        expected_sender=sender["reference"],
    ) is None
    assert service.wait_read(sender_context, batch, "all", 0)["unread_instances"]

    claimed = service._claim_receive_candidate(
        recipient_context,
        message_id,
        expected_name="invite",
        expected_sender=sender["reference"],
    )
    assert claimed is not None and claimed["content"] == {"secret": "body"}
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True
    assert service._claim_receive_candidate(
        recipient_context, message_id,
    ) is None

    damaged = _send(service, sender_context, recipient, {"value": 2})
    with sqlite3.connect(service.database_path) as connection:
        connection.execute(
            "UPDATE message_batches SET content_json='not-json' WHERE batch_id=?",
            (damaged["batch_id"],),
        )
    with pytest.raises(MessageRuntimeError) as error:
        service._peek_receive_candidates(
            recipient_context, "invite", sender["reference"],
        )
    assert error.value.error_id == "message.decode_failed"
    assert service.wait_read(
        sender_context, damaged, "all", 0,
    )["unread_instances"]


def test_listener_immediate_handler_argument_and_main_flow_resume(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"room": "001"})
    message_id = batch["recipients"][0]["message_id"]
    handler = [_log(
        "handler.log",
        {
            "kind": "member_access",
            "source": _reference("message"),
            "field_id": "message_id",
        },
    )]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(
            _ecir(
                [_listener(sender["reference"]), _log("main.after", "main resumed")],
                handler,
                project_path=str(tmp_path),
            ),
            message_context=recipient_context,
        )["execution_id"],
    )

    assert result["status"] == "completed", result
    events = result["events"]
    handler_sequence = next(
        item["sequence"] for item in events
        if item["instruction_id"] == "handler.log" and item["message"] == message_id
    )
    main_sequence = next(
        item["sequence"] for item in events if item["instruction_id"] == "main.after"
    )
    assert handler_sequence < main_sequence
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True
    assert all("room" not in item["message"] for item in events)


def test_listener_condition_delays_ack_and_is_not_evaluated_without_candidate(
    tmp_path: Path,
) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"room": "002"})
    ready_variable = [{
        "variable_id": "ready",
        "display_name": "可处理",
        "value_type": "bool",
        "default_value": False,
        "constraints": {},
    }]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(
            _ecir(
                [
                    _listener(
                        sender["reference"],
                        condition=_reference("ready", scope="project"),
                    ),
                    _log("main.before-ready", "not ready"),
                    _instruction(
                        "main.ready",
                        "data.assign_project",
                        {"target": {"variable_id": "ready"}, "value": True},
                    ),
                    _log("main.after-ready", "after ready"),
                ],
                [_log("handler.ready", "handled")],
                project_path=str(tmp_path),
                project_variables=ready_variable,
            ),
            message_context=recipient_context,
        )["execution_id"],
    )
    assert result["status"] == "completed", result
    sequences = {
        item["instruction_id"]: item["sequence"]
        for item in result["events"]
        if item["instruction_id"] in {
            "main.before-ready", "handler.ready", "main.after-ready",
        }
    }
    assert (
        sequences["main.before-ready"]
        < sequences["handler.ready"]
        < sequences["main.after-ready"]
    )
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True

    # An unset reference would fail immediately if an idle listener evaluated
    # its condition without first finding a candidate.
    idle_runtime = VNextRuntime(persist_event_log=False)
    idle = _terminal(
        idle_runtime,
        idle_runtime.start(
            _ecir(
                [_listener(condition=_reference("never_bound"))],
                [_log("handler.never", "unexpected")],
            ),
            message_context=recipient_context,
        )["execution_id"],
    )
    assert idle["status"] == "completed", idle

    blocked_batch = _send(
        service, sender_context, recipient, {"room": "not-ready"},
    )
    blocked_runtime = VNextRuntime(persist_event_log=False)
    blocked = _terminal(
        blocked_runtime,
        blocked_runtime.start(
            _ecir(
                [_listener(sender["reference"], condition=False)],
                [_log("handler.blocked", "unexpected")],
            ),
            message_context=recipient_context,
        )["execution_id"],
    )
    assert blocked["status"] == "completed", blocked
    assert not any(
        item["instruction_id"] == "handler.blocked" for item in blocked["events"]
    )
    assert service.wait_read(
        sender_context, blocked_batch, "all", 0,
    )["unread_instances"]


def test_listener_fifo_non_reentrant_and_new_arrival_waits_for_next_batch(
    tmp_path: Path,
) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    first = _send(service, sender_context, recipient, {"order": 1})
    first_id = first["recipients"][0]["message_id"]
    handler = [_instruction(
        "handler.wait",
        "wait.duration",
        {"official.wait.duration.parameter.duration": {"kind": "duration", "milliseconds": 180}},
    )]
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _ecir(
            [_listener(sender["reference"]), _log("main.between-batches", "main")],
            handler,
            project_path=str(tmp_path),
        ),
        message_context=recipient_context,
    )["execution_id"]

    def first_claimed() -> bool:
        return any(
            first_id in item["message"] and "接手消息" in item["message"]
            for item in runtime.snapshot(execution_id)["events"]
        )

    _wait_for(first_claimed)
    second = _send(service, sender_context, recipient, {"order": 2})
    second_id = second["recipients"][0]["message_id"]
    result = _terminal(runtime, execution_id)
    assert result["status"] == "completed", result

    positions: dict[str, int] = {}
    for item in result["events"]:
        message = item["message"]
        if first_id in message and "接手消息" in message:
            positions["claim_first"] = item["sequence"]
        elif first_id in message and "处理完成" in message:
            positions["complete_first"] = item["sequence"]
        elif second_id in message and "接手消息" in message:
            positions["claim_second"] = item["sequence"]
        elif second_id in message and "处理完成" in message:
            positions["complete_second"] = item["sequence"]
        elif item["instruction_id"] == "main.between-batches":
            positions["main"] = item["sequence"]
    assert (
        positions["claim_first"]
        < positions["complete_first"]
        < positions["main"]
        < positions["claim_second"]
        < positions["complete_second"]
    )


def test_listener_cancel_and_handler_failure_do_not_requeue_claimed_message(
    tmp_path: Path,
) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    cancelled_batch = _send(service, sender_context, recipient, {"secret": "cancel"})
    cancelled_id = cancelled_batch["recipients"][0]["message_id"]
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _ecir(
            [_listener(sender["reference"]), _log("main.cancel.unreachable", "no")],
            [_instruction(
                "handler.long",
                "wait.duration",
                {"official.wait.duration.parameter.duration": {"kind": "duration", "milliseconds": 5_000}},
            )],
            project_path=str(tmp_path),
        ),
        message_context=recipient_context,
    )["execution_id"]
    _wait_for(lambda: any(
        cancelled_id in item["message"] and "接手消息" in item["message"]
        for item in runtime.snapshot(execution_id)["events"]
    ))
    runtime.cancel(execution_id)
    cancelled = _terminal(runtime, execution_id)
    assert cancelled["status"] == "cancelled", cancelled
    assert cancelled["current_listener_id"] == "listener.invite"
    assert cancelled["current_message_id"] == cancelled_id
    assert any("监听处理被取消" in item["message"] for item in cancelled["events"])
    assert service.wait_read(
        sender_context, cancelled_batch, "all", 0,
    )["condition_met"] is True

    failed_batch = _send(service, sender_context, recipient, {"secret": "failure"})
    failed_id = failed_batch["recipients"][0]["message_id"]
    failed_runtime = VNextRuntime(persist_event_log=False)
    failed = _terminal(
        failed_runtime,
        failed_runtime.start(
            _ecir(
                [_listener(sender["reference"]), _log("main.failure.unreachable", "no")],
                [_instruction("handler.failure", "control.target_scope", {})],
                project_path=str(tmp_path),
            ),
            message_context=recipient_context,
        )["execution_id"],
    )
    assert failed["status"] == "failed", failed
    assert failed["error_id"] == "target.reference_invalid"
    assert failed["current_listener_id"] == "listener.invite"
    assert failed["current_message_id"] == failed_id
    assert service.wait_read(
        sender_context, failed_batch, "all", 0,
    )["condition_met"] is True
    with zipfile.ZipFile(failed_runtime.diagnostic_path(failed["execution_id"])) as archive:
        report = json.loads(archive.read("report.json"))
    assert report["listener_id"] == "listener.invite"
    assert report["message_id"] == failed_id
    assert [item["function_id"] for item in report["call_stack"]] == [
        "function.main", "function.handler",
    ]
    assert "failure" not in json.dumps(report["variables"], ensure_ascii=False)


def test_listener_handler_failure_uses_normal_try_catch_semantics(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"value": 1})
    tried = _instruction(
        "main.try",
        "control.try",
        {
            "body": [
                _listener(sender["reference"]),
                _log("main.trigger", "trigger"),
            ],
            "retry_policy": None,
            "catches": [{
                "catch_id": "catch.handler",
                "error_ids": ["target.reference_invalid"],
                "error_slot": "caught_error",
                "body": [_log("main.caught", "caught")],
            }],
            "finally": [],
        },
    )
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(
            _ecir(
                [tried, _log("main.after-catch", "continued")],
                [_instruction("handler.failure", "control.target_scope", {})],
            ),
            message_context=recipient_context,
        )["execution_id"],
    )
    assert result["status"] == "completed", result
    assert result["current_listener_id"] == ""
    assert any(item["instruction_id"] == "main.caught" for item in result["events"])
    assert any(item["instruction_id"] == "main.after-catch" for item in result["events"])
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True


def test_pause_resume_keeps_candidate_unread_until_resumed(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _ecir(
            [
                _listener(sender["reference"]),
                _instruction(
                    "main.wait",
                    "wait.duration",
                    {"official.wait.duration.parameter.duration": {"kind": "duration", "milliseconds": 1_000}},
                ),
            ],
            [_log("handler.paused", "handled")],
        ),
        message_context=recipient_context,
    )["execution_id"]
    _wait_for(lambda: runtime.snapshot(execution_id)["status"] == "running")
    runtime.pause(execution_id)
    _wait_for(lambda: runtime.snapshot(execution_id)["status"] == "paused")
    batch = _send(service, sender_context, recipient, {"value": "paused"})
    assert service.wait_read(sender_context, batch, "all", 0)["unread_instances"]
    runtime.resume(execution_id)
    result = _terminal(runtime, execution_id)
    assert result["status"] == "completed", result
    assert any(item["instruction_id"] == "handler.paused" for item in result["events"])
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True


class _AtomicDriver:
    platform = "windows"

    def __init__(
        self,
        target_id: str,
        order: list[str],
        started: threading.Event | None = None,
    ) -> None:
        self.target = {"target_id": target_id, "type": "windows"}
        self.order = order
        self.started = started

    def supports(self, opcode: str) -> bool:
        return opcode in {"input.click", "probe.listener", "probe.target"}

    def execute(self, opcode: str, _arguments: dict[str, Any], _cancelled) -> None:
        if opcode == "input.click":
            self.order.append("click.start")
            if self.started is not None:
                self.started.set()
            time.sleep(0.15)
            self.order.append("click.end")
        elif opcode == "probe.listener":
            self.order.append("listener")
        else:
            self.order.append(f"target:{self.target['target_id']}")

    def capture_frame(self) -> object:
        return object()

    def close(self) -> None:
        return None


def test_atomic_driver_action_is_not_interrupted_by_listener(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    order: list[str] = []
    started = threading.Event()
    driver = _AtomicDriver("target.one", order, started)
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _ecir(
            [
                _listener(sender["reference"]),
                _instruction("main.click", "input.click", {}),
                _log("main.after-click", "after"),
            ],
            [_instruction("handler.probe", "probe.listener", {})],
        ),
        driver=driver,
        message_context=recipient_context,
    )["execution_id"]
    assert started.wait(2)
    batch = _send(service, sender_context, recipient, {"during": "click"})
    result = _terminal(runtime, execution_id)
    assert result["status"] == "completed", result
    assert order == ["click.start", "click.end", "listener"]
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True


def test_listener_handler_uses_current_target_scope_serially(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"scope": 2})
    order: list[str] = []
    initial = _AtomicDriver("target.one", order)

    def factory(_project_path: str, target: dict[str, Any]) -> _AtomicDriver:
        return _AtomicDriver(str(target["target_id"]), order)

    scoped_listener = _listener(
        sender["reference"],
        handler_arguments={},
    )
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(
            _ecir(
                [_instruction(
                    "scope.two",
                    "control.target_scope",
                    {
                        "target": {"kind": "target_ref", "target_id": "target.two"},
                        "body": [scoped_listener],
                    },
                )],
                [_instruction("handler.target", "probe.target", {})],
                targets=[
                    {"target_id": "target.one", "type": "windows"},
                    {"target_id": "target.two", "type": "windows"},
                ],
            ),
            driver=initial,
            target_driver_factory=factory,
            message_context=recipient_context,
        )["execution_id"],
    )
    assert result["status"] == "completed", result
    assert "target:target.two" in order
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True


def _compiled_listener_documents(
    *,
    wait_name: StringValue | SymbolReferenceValue | None = None,
    listen_name: StringValue | SymbolReferenceValue | None = None,
    wait_sender: EntityReferenceValue | None = None,
    listen_sender: EntityReferenceValue | None = None,
    dynamic_parameter: ProgramParameter | None = None,
) -> tuple[ProgramDocument, ProgramDocument]:
    handler_parameter = ProgramParameter(
        parameter_id="handler.message",
        symbol_id="message",
        display_name="消息",
        value_type="received_message",
    )
    handler = ProgramDocument(
        document_id="document_handler",
        function=ProgramFunction(
            function_id="function.handler",
            display_name="处理邀请",
            parameters=(handler_parameter,),
            statements=(CallStatement(
                statement_id="handler.log",
                function_id=LOG_OUTPUT_FUNCTION_ID,
                arguments={
                    LOG_OUTPUT_CONTENT_PARAMETER_ID: StringValue(
                        value_id="handler.log.value",
                        value="handled",
                    ),
                },
            ),),
        ),
    )
    statements: list[Any] = []
    if wait_name is not None:
        wait_arguments: dict[str, Any] = {
            "official.message.wait_receive.parameter.name": wait_name,
        }
        if wait_sender is not None:
            wait_arguments["official.message.wait_receive.parameter.sender"] = wait_sender
        statements.append(CallStatement(
            statement_id="main.wait-receive",
            function_id="official.message.wait_receive",
            arguments=wait_arguments,
        ))
    statements.extend((
        ListenStatement(
            statement_id="main.listener",
            event_source=MessageEventSource(
                name=listen_name or StringValue(
                    value_id="main.listen.name", value="invite",
                ),
                sender=listen_sender,
            ),
            receive_binding=LoopBinding(
                symbol_id="received",
                display_name="收到的消息",
                value_type="received_message",
            ),
            handler_function_id="function.handler",
            handler_arguments={
                "handler.message": SymbolReferenceValue(
                    value_id="main.listen.handler-message",
                    symbol_id="received",
                    value_type="received_message",
                ),
            },
        ),
        CallStatement(
            statement_id="main.log-after",
            function_id=LOG_OUTPUT_FUNCTION_ID,
            arguments={
                LOG_OUTPUT_CONTENT_PARAMETER_ID: StringValue(
                    value_id="main.log-after.value",
                    value="main resumed",
                ),
            },
        ),
    ))
    main = ProgramDocument(
        document_id="document_main",
        function=ProgramFunction(
            function_id="function.main",
            display_name="主程序",
            parameters=((dynamic_parameter,) if dynamic_parameter else ()),
            statements=tuple(statements),
        ),
    )
    return main, handler


def test_compiled_listen_bundle_is_executable_and_listen_only_needs_message_context(
    tmp_path: Path,
) -> None:
    service, _sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    main, handler = _compiled_listener_documents()
    compiled = compile_program_bundle(
        [main, handler],
        official_function_registry_v6,
        entry_function_id="function.main",
        target_platform="no_target",
    )
    assert compiled["valid"] is True, compiled["diagnostics"]
    plan = adapt_program_ecir_for_runtime(
        compiled["ecir"], project_path=str(tmp_path),
    )
    assert program_uses_messages(plan) is True
    assert "messaging" in plan["required_capabilities"]
    assert plan["minimum_android_api"] == 23
    assert {item["function_id"] for item in plan["functions"]} == {
        "function.main", "function.handler",
    }
    batch = _send(service, sender_context, recipient, {"compiled": True})
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(plan, message_context=recipient_context)["execution_id"],
    )
    assert result["status"] == "completed", result
    assert service.wait_read(sender_context, batch, "all", 0)["condition_met"] is True
    assert any(item["instruction_id"] == "handler.log" for item in result["events"])
    assert any(item["instruction_id"] == "main.log-after" for item in result["events"])


def test_compiler_rejects_static_and_dynamic_wait_listen_consumer_conflicts() -> None:
    same_wait_sender = EntityReferenceValue(
        value_id="main.wait.sender",
        reference_id="instance_sender",
        reference_type="instance_ref",
    )
    same_listen_sender = EntityReferenceValue(
        value_id="main.listen.sender",
        reference_id="instance_sender",
        reference_type="instance_ref",
    )
    main, handler = _compiled_listener_documents(
        wait_name=StringValue(value_id="main.wait.name", value="invite"),
        listen_name=StringValue(value_id="main.listen.name", value="invite"),
        wait_sender=same_wait_sender,
        listen_sender=same_listen_sender,
    )
    static = compile_program_bundle(
        [main, handler],
        official_function_registry_v6,
        entry_function_id="function.main",
    )
    assert static["valid"] is False
    assert any(item["code"] == "PGM-MSG-001" for item in static["diagnostics"])

    dynamic_parameter = ProgramParameter(
        parameter_id="main.parameter.message-name",
        symbol_id="message_name",
        display_name="消息名称",
        value_type="string",
    )
    dynamic_name = SymbolReferenceValue(
        value_id="main.wait.dynamic-name",
        symbol_id="message_name",
        value_type="string",
    )
    dynamic_main, dynamic_handler = _compiled_listener_documents(
        wait_name=dynamic_name,
        listen_name=StringValue(value_id="main.listen.name.dynamic", value="invite"),
        dynamic_parameter=dynamic_parameter,
    )
    dynamic = compile_program_bundle(
        [dynamic_main, dynamic_handler],
        official_function_registry_v6,
        entry_function_id="function.main",
    )
    assert dynamic["valid"] is False
    assert any(item["code"] == "PGM-MSG-002" for item in dynamic["diagnostics"])

    disjoint_main, disjoint_handler = _compiled_listener_documents(
        wait_name=StringValue(value_id="main.wait.name.disjoint", value="other"),
        listen_name=StringValue(value_id="main.listen.name.disjoint", value="invite"),
    )
    disjoint = compile_program_bundle(
        [disjoint_main, disjoint_handler],
        official_function_registry_v6,
        entry_function_id="function.main",
    )
    assert disjoint["valid"] is True, disjoint["diagnostics"]


def test_listener_runs_across_isolated_worker_process(tmp_path: Path) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    batch = _send(service, sender_context, recipient, {"worker": True})
    runtime = VNextRuntime(use_worker_process=True, persist_event_log=False)
    try:
        started = runtime.start(
            _ecir(
                [_listener(sender["reference"]), _log("main.worker", "resumed")],
                [_log("handler.worker", "handled")],
                project_path=str(tmp_path),
            ),
            execution_id="execution_listener_worker",
            message_context=recipient_context,
        )
        result = _terminal(runtime, started["execution_id"], timeout=12)
        assert result["status"] == "completed", result
        assert result["worker"]["started"] is True
        assert any(
            item["instruction_id"] == "handler.worker" for item in result["events"]
        )
        assert service.wait_read(
            sender_context, batch, "all", 0,
        )["condition_met"] is True
    finally:
        runtime.shutdown()


def test_listener_worker_pause_resume_and_cancel_keep_queue_state_consistent(
    tmp_path: Path,
) -> None:
    service, sender, sender_context, recipient, recipient_context = _service_world(
        tmp_path,
    )
    runtime = VNextRuntime(use_worker_process=True, persist_event_log=False)
    try:
        paused_id = runtime.start(
            _ecir(
                [
                    _listener(sender["reference"]),
                    _instruction(
                        "main.worker-wait",
                        "wait.duration",
                        {
                            "official.wait.duration.parameter.duration": {
                                "kind": "duration", "milliseconds": 1_000,
                            },
                        },
                    ),
                ],
                [_log("handler.worker-paused", "handled")],
                project_path=str(tmp_path),
            ),
            execution_id="execution_listener_worker_pause",
            message_context=recipient_context,
        )["execution_id"]
        _wait_for(lambda: (
            runtime.snapshot(paused_id)["worker"]["started"]
            and runtime.snapshot(paused_id)["status"] == "running"
        ), timeout=6)
        runtime.pause(paused_id)
        _wait_for(
            lambda: runtime.snapshot(paused_id)["status"] == "paused",
            timeout=6,
        )
        paused_batch = _send(
            service, sender_context, recipient, {"worker": "paused"},
        )
        assert service.wait_read(
            sender_context, paused_batch, "all", 0,
        )["unread_instances"]
        runtime.resume(paused_id)
        resumed = _terminal(runtime, paused_id, timeout=10)
        assert resumed["status"] == "completed", resumed
        assert any(
            item["instruction_id"] == "handler.worker-paused"
            for item in resumed["events"]
        )

        cancelled_batch = _send(
            service, sender_context, recipient, {"worker": "cancelled"},
        )
        cancelled_message_id = cancelled_batch["recipients"][0]["message_id"]
        cancelled_id = runtime.start(
            _ecir(
                [_listener(sender["reference"]), _log("main.worker-unreachable", "no")],
                [_instruction(
                    "handler.worker-long",
                    "wait.duration",
                    {
                        "official.wait.duration.parameter.duration": {
                            "kind": "duration", "milliseconds": 5_000,
                        },
                    },
                )],
                project_path=str(tmp_path),
            ),
            execution_id="execution_listener_worker_cancel",
            message_context=recipient_context,
        )["execution_id"]
        _wait_for(lambda: any(
            cancelled_message_id in item["message"] and "接手消息" in item["message"]
            for item in runtime.snapshot(cancelled_id)["events"]
        ), timeout=8)
        runtime.cancel(cancelled_id)
        cancelled = _terminal(runtime, cancelled_id, timeout=10)
        assert cancelled["status"] == "cancelled", cancelled
        assert cancelled["current_listener_id"] == "listener.invite"
        assert cancelled["current_message_id"] == cancelled_message_id
        assert service.wait_read(
            sender_context, cancelled_batch, "all", 0,
        )["condition_met"] is True

        crashed_batch = _send(
            service, sender_context, recipient, {"worker": "crashed"},
        )
        crashed_message_id = crashed_batch["recipients"][0]["message_id"]
        crashed_id = runtime.start(
            _ecir(
                [_listener(sender["reference"]), _log("main.worker-crash", "no")],
                [_instruction(
                    "handler.worker-crash",
                    "wait.duration",
                    {
                        "official.wait.duration.parameter.duration": {
                            "kind": "duration", "milliseconds": 5_000,
                        },
                    },
                )],
                project_path=str(tmp_path),
            ),
            execution_id="execution_listener_worker_crash",
            message_context=recipient_context,
        )["execution_id"]
        _wait_for(lambda: (
            runtime.snapshot(crashed_id)["current_message_id"] == crashed_message_id
            and any(
                crashed_message_id in item["message"] and "接手消息" in item["message"]
                for item in runtime.snapshot(crashed_id)["events"]
            )
        ), timeout=8)
        runtime._sessions[crashed_id]._worker_proxy.terminate_tree()
        crashed = _terminal(runtime, crashed_id, timeout=10)
        assert crashed["status"] == "failed", crashed
        assert service.wait_read(
            sender_context, crashed_batch, "all", 0,
        )["condition_met"] is True
        crash_events = [
            item["message"] for item in crashed["events"]
            if item["level"] == "error" and "Worker" in item["message"]
        ]
        assert crash_events
        assert "listener_id=listener.invite" in crash_events[-1]
        assert f"message_id={crashed_message_id}" in crash_events[-1]
        assert "function.handler" in crash_events[-1]
    finally:
        runtime.shutdown()
