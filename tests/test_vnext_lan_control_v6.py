from __future__ import annotations

import ipaddress
import multiprocessing
import socket
import struct
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_player_lan_router import create_vnext_player_lan_router
from core.vnext.lan_control_v6 import LanControlError, LanControlPlaneV6
from core.vnext.lan_schedule_v6 import (
    LanDispatchRouterV6,
    LanScheduleInboundV6,
    LanScheduleReferenceResolverV6,
)
from core.vnext.message_runtime_v6 import MessageRuntimeError, MessageRuntimeV6
from core.vnext.schedule_v6 import (
    LocalDispatchRequest,
    ScheduleServiceV6,
    SQLiteLocalDispatchGateway,
    StaticScheduleReferenceResolver,
    VirtualClock,
)
from core.vnext.schedule_hub_v6 import PlayerHubV6


def _control(root: Path, host: str = "127.0.0.1") -> LanControlPlaneV6:
    return LanControlPlaneV6(
        root,
        bind_host=host,
        advertised_addresses=[host],
    )


def _pair(
    initiator: LanControlPlaneV6,
    receiver: LanControlPlaneV6,
    *,
    initiator_grants: dict[str, Any] | None = None,
    receiver_grants: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    offer = receiver.create_pairing_session()
    pending = initiator.begin_pairing(
        address=str(receiver._local_addresses()[0]),
        port=receiver.port,
        code=offer["code"],
        session_id=offer["session_id"],
        permissions=initiator_grants or {},
    )
    receiver.directory.confirm_pairing(
        pending["pending_id"], receiver_grants or {}
    )
    peer = initiator.complete_pairing(
        pending,
        expected_fingerprint=receiver.identity.fingerprint,
    )
    return peer, pending


def _context(instance: dict[str, Any]) -> dict[str, str]:
    return {
        "project_namespace": str(instance["project_namespace"]),
        "host_id": str(instance["host_id"]),
        "instance_id": str(instance["instance_id"]),
    }


def _message_child(root_text: str, pipe: Any) -> None:
    root = Path(root_text)
    control = _control(root / "lan")
    runtime = MessageRuntimeV6(root / "messages.sqlite3", lan_control=control)
    receiver = runtime.register_instance(
        "product", "第二进程收件实例", endpoint_key="child-receiver"
    )
    control.set_status_provider(lambda: {"instances": runtime.catalog_instances()})
    try:
        control.start()
        pipe.send(
            {
                "port": control.port,
                "host_id": control.identity.host_id,
                "fingerprint": control.identity.fingerprint,
                "receiver": receiver,
            }
        )
        while True:
            command = pipe.recv()
            if command[0] == "session":
                pipe.send(control.create_pairing_session())
            elif command[0] == "confirm":
                pipe.send(
                    control.directory.confirm_pairing(
                        command[1],
                        {"messages": True, "status": True},
                    )
                )
            elif command[0] == "receive":
                pipe.send(
                    runtime.wait_receive(
                        _context(receiver), command[1], timeout_ms=3_000
                    )
                )
            elif command[0] == "stop":
                break
    finally:
        control.stop()
        pipe.close()


def test_identity_pairing_permissions_replay_and_revoke(tmp_path: Path) -> None:
    identity_root = tmp_path / "stable"
    first = _control(identity_root)
    stable = (first.identity.host_id, first.identity.fingerprint)
    first.stop()
    restarted = _control(identity_root)
    assert (restarted.identity.host_id, restarted.identity.fingerprint) == stable

    left = _control(tmp_path / "left", "127.0.0.1")
    right = _control(tmp_path / "right", "127.0.0.2")
    calls: list[dict[str, Any]] = []
    right.register_handler(
        "message.echo", lambda _peer, payload: calls.append(payload) or payload
    )
    try:
        left.start()
        right.start()
        discovered = left.discover(
            addresses=["127.0.0.2"], port=right.port, timeout_seconds=0.5
        )
        assert any(item["host_id"] == right.identity.host_id for item in discovered)
        _pair(
            left,
            right,
            initiator_grants={"messages": True},
            receiver_grants={"messages": True, "status": True},
        )
        peer = left.directory.peer(right.identity.host_id)
        assert peer["remote_permissions"]["messages"] is True
        assert peer["remote_permissions"]["remote_start"] is False
        assert left.secure_request(
            right.identity.host_id,
            "message.echo",
            {"value": 7},
            request_id="request-replay",
        ) == {"value": 7}
        assert left.secure_request(
            right.identity.host_id,
            "message.echo",
            {"value": 7},
            request_id="request-replay",
        ) == {"value": 7}
        assert calls == [{"value": 7}]
        with pytest.raises(LanControlError) as conflict:
            left.secure_request(
                right.identity.host_id,
                "message.echo",
                {"value": 8},
                request_id="request-replay",
            )
        assert conflict.value.error_id == "lan.replay_conflict"

        # A truncated/half connection never damages the next authenticated one.
        with socket.create_connection(("127.0.0.2", right.port), timeout=2) as half:
            half.sendall(struct.pack("!I", 128) + b"short")
        assert left.refresh_peer_status(right.identity.host_id)["instances"] == []

        revoked = right.directory.revoke(left.identity.host_id)
        assert revoked["ok"] is True
        with pytest.raises(LanControlError) as denied:
            left.refresh_peer_status(right.identity.host_id)
        assert denied.value.error_id == "lan.peer_unknown"
        assert right.directory.list_remote_instances() == []
    finally:
        left.stop()
        right.stop()


def test_pairing_code_expiry_and_fingerprint_confirmation(tmp_path: Path) -> None:
    left = _control(tmp_path / "left")
    right = _control(tmp_path / "right")
    try:
        left.start()
        right.start()
        expired = right.create_pairing_session(ttl_ms=1)
        time.sleep(0.01)
        with pytest.raises(LanControlError) as timeout:
            left.begin_pairing(
                address="127.0.0.1",
                port=right.port,
                code=expired["code"],
                session_id=expired["session_id"],
            )
        assert timeout.value.error_id == "lan.pairing_code_invalid"

        offer = right.create_pairing_session()
        pending = left.begin_pairing(
            address="127.0.0.1",
            port=right.port,
            code=offer["code"],
            session_id=offer["session_id"],
        )
        tampered = {**pending, "expires_at": "2099-01-01T00:00:00Z"}
        with pytest.raises(LanControlError) as unauthenticated:
            left._verify_pairing_response(
                tampered,
                session_id=offer["session_id"],
                code=offer["code"],
            )
        assert unauthenticated.value.error_id == "lan.authentication_failed"
        right.directory.confirm_pairing(pending["pending_id"], {})
        with pytest.raises(LanControlError) as mismatch:
            left.complete_pairing(pending, expected_fingerprint="SHA256:wrong")
        assert mismatch.value.error_id == "lan.fingerprint_mismatch"
    finally:
        left.stop()
        right.stop()


def test_peer_permission_refresh_recovers_after_remote_grant_changes(tmp_path: Path) -> None:
    left = _control(tmp_path / "left")
    right = _control(tmp_path / "right")
    right.set_status_provider(lambda: {"instances": []})
    try:
        left.start()
        right.start()
        _pair(
            left,
            right,
            initiator_grants={"messages": True, "status": True},
            receiver_grants={"messages": True, "status": False},
        )
        assert left.directory.peer(right.identity.host_id)["remote_permissions"]["status"] is False

        right.directory.set_permissions(
            left.identity.host_id, {"messages": True, "status": True}
        )
        assert left.refresh_peer_status(right.identity.host_id) == {"instances": []}
        assert left.directory.peer(right.identity.host_id)["remote_permissions"]["status"] is True
    finally:
        left.stop()
        right.stop()


def test_local_message_auto_trust_is_limited_to_signed_product_domain(
    tmp_path: Path,
) -> None:
    runtime = MessageRuntimeV6(tmp_path / "messages.sqlite3")
    first = runtime.register_instance(
        "product",
        "签名产品实例一",
        endpoint_key="signed-one",
        endpoint_kind="player",
        trust_domain="product_signature_a",
    )
    second = runtime.register_instance(
        "product",
        "签名产品实例二",
        endpoint_key="signed-two",
        endpoint_kind="player",
        trust_domain="product_signature_a",
    )
    impostor = runtime.register_instance(
        "product",
        "不同签名实例",
        endpoint_key="other-signature",
        endpoint_kind="player",
        trust_domain="product_signature_b",
    )

    delivered = runtime.send(
        _context(first), [second["reference"]], "本机可信", {"ok": True}
    )
    assert delivered["recipients"][0]["transport"] == "local"
    before = len(runtime.diagnostic_snapshot("product")["messages"])
    with pytest.raises(MessageRuntimeError) as denied:
        runtime.send(_context(first), [impostor["reference"]], "不可信", {})
    assert denied.value.error_id == "message.instance_unknown"
    assert len(runtime.diagnostic_snapshot("product")["messages"]) == before


def test_message_multi_recipient_read_cancel_offline_ttl_and_permissions(
    tmp_path: Path,
) -> None:
    left = _control(tmp_path / "left-lan")
    right = _control(tmp_path / "right-lan")
    sender_runtime = MessageRuntimeV6(
        tmp_path / "left-messages.sqlite3", lan_control=left
    )
    receiver_runtime = MessageRuntimeV6(
        tmp_path / "right-messages.sqlite3", lan_control=right
    )
    sender = sender_runtime.register_instance(
        "product", "发送实例", endpoint_key="sender"
    )
    local = sender_runtime.register_instance(
        "product", "本机收件", endpoint_key="local-recipient"
    )
    remote_one = receiver_runtime.register_instance(
        "product", "远端一号", endpoint_key="remote-one"
    )
    remote_two = receiver_runtime.register_instance(
        "product", "远端二号", endpoint_key="remote-two"
    )
    right.set_status_provider(
        lambda: {"instances": receiver_runtime.catalog_instances()}
    )
    try:
        left.start()
        right.start()
        _pair(
            left,
            right,
            initiator_grants={"messages": True, "status": True},
            receiver_grants={"messages": True, "status": True},
        )
        left.refresh_peer_status(right.identity.host_id)
        batch = sender_runtime.send(
            _context(sender),
            [local["reference"], remote_one["reference"], remote_two["reference"]],
            "工作通知",
            {"items": [1, 2, 3]},
            ttl_ms=3_000,
        )
        assert [item["transport"] for item in batch["recipients"]] == [
            "local",
            "lan",
            "lan",
        ]
        received = receiver_runtime.wait_receive(
            _context(remote_one), "工作通知", timeout_ms=1_000
        )
        assert received and received["content"] == {"items": [1, 2, 3]}
        any_read = sender_runtime.wait_read(
            _context(sender), batch, mode="any", timeout_ms=2_000
        )
        assert any_read["condition_met"] is True
        sender_runtime.cancel(_context(sender), batch, remote_two["reference"])
        sender_runtime.cancel(_context(sender), batch, local["reference"])
        terminal = sender_runtime.wait_read(
            _context(sender), batch, mode="all", timeout_ms=2_000
        )
        assert terminal["terminal"] is True
        assert len(terminal["read_instances"]) == 1
        assert len(terminal["cancelled_instances"]) == 2

        # A known offline recipient is durable and resumes with the original ID.
        old_port = right.port
        right.stop()
        queued = sender_runtime.send(
            _context(sender),
            [remote_one["reference"]],
            "离线补发",
            {"sequence": 1},
            ttl_ms=6_000,
        )
        queued_id = queued["recipients"][0]["message_id"]
        assert queued["recipients"][0]["status"] == "waiting_send"
        right.requested_port = old_port
        right.start()
        deadline = time.monotonic() + 2
        received = None
        while time.monotonic() < deadline:
            sender_runtime.flush_outbox(force=True)
            received = receiver_runtime.wait_receive(
                _context(remote_one), "离线补发", timeout_ms=50
            )
            if received:
                break
        assert received and received["message_id"] == queued_id

        right.stop()
        expiring = sender_runtime.send(
            _context(sender),
            [remote_one["reference"]],
            "短消息",
            None,
            ttl_ms=20,
        )
        time.sleep(0.04)
        sender_runtime.flush_outbox(force=True)
        expired = sender_runtime.wait_read(
            _context(sender), expiring, timeout_ms=0
        )
        assert len(expired["expired_instances"]) == 1
    finally:
        left.stop()
        right.stop()

    # Pairing without a message grant must fail before creating a queue row.
    no_grant_left = _control(tmp_path / "no-grant-left")
    no_grant_right = _control(tmp_path / "no-grant-right")
    no_grant_runtime = MessageRuntimeV6(
        tmp_path / "no-grant.sqlite3", lan_control=no_grant_left
    )
    no_grant_sender = no_grant_runtime.register_instance(
        "product", "无权限发送者", endpoint_key="no-grant"
    )
    try:
        no_grant_left.start()
        no_grant_right.start()
        _pair(no_grant_left, no_grant_right)
        no_grant_left.directory.update_remote_catalog(
            no_grant_right.identity.host_id,
            {
                "instances": [
                    {
                        "project_namespace": "product",
                        "instance_id": "known-remote",
                        "display_name": "已知但未授权",
                        "product_id": "product",
                    }
                ]
            },
        )
        reference = MessageRuntimeV6._reference(
            no_grant_right.identity.host_id, "known-remote"
        )
        with pytest.raises(MessageRuntimeError) as denied:
            no_grant_runtime.send(
                _context(no_grant_sender), [reference], "拒绝", {}
            )
        assert denied.value.error_id == "message.instance_unknown"
        assert no_grant_runtime.diagnostic_snapshot("product")["messages"] == []
    finally:
        no_grant_left.stop()
        no_grant_right.stop()


def test_remote_dispatch_is_privileged_and_idempotent(tmp_path: Path) -> None:
    coordinator = _control(tmp_path / "coordinator")
    target = _control(tmp_path / "target")
    launches: list[str] = []
    local_gateway = SQLiteLocalDispatchGateway(
        tmp_path / "coordinator.sqlite3", launcher=lambda _request, run_id: launches.append(run_id)
    )
    target_gateway = SQLiteLocalDispatchGateway(
        tmp_path / "target.sqlite3", launcher=lambda _request, run_id: launches.append(run_id)
    )
    LanScheduleInboundV6(target, target_gateway)
    target.set_status_provider(
        lambda: {
            "instances": [
                {
                    "project_namespace": "product",
                    "instance_id": "instance",
                    "display_name": "目标实例",
                    "product_id": "product",
                    "profiles": [{"profile_id": "profile", "name": "默认方案"}],
                    "status": "ready",
                }
            ]
        }
    )
    try:
        coordinator.start()
        target.start()
        _pair(
            coordinator,
            target,
            initiator_grants={"messages": True},
            receiver_grants={
                "status": True,
                "remote_start": True,
                "allowed_products": ["product"],
                "allowed_instances": ["instance"],
            },
        )
        router = LanDispatchRouterV6(
            coordinator.identity.host_id, local_gateway, coordinator
        )
        request = LocalDispatchRequest(
            dispatch_id="dispatch-stable",
            occurrence_id="occurrence-stable",
            schedule_id="schedule-stable",
            schedule_revision=1,
            entry_id="entry-stable",
            host_id=target.identity.host_id,
            instance_id="instance",
            product_id="product",
            profile_id="profile",
            requested_at="first-observation",
        )
        first = router.accept(request)
        retry = router.accept(
            LocalDispatchRequest(**{**request.as_dict(), "requested_at": "after-ack-loss"})
        )
        assert retry.run_id == first.run_id
        assert launches == [first.run_id]

        coordinator.refresh_peer_status(target.identity.host_id)
        clock = VirtualClock("2026-09-01T00:00:00Z")
        service = ScheduleServiceV6(
            tmp_path / "remote-schedules.sqlite3",
            clock=clock,
            resolver=LanScheduleReferenceResolverV6(
                StaticScheduleReferenceResolver({}),
                coordinator.identity.host_id,
                coordinator,
            ),
            dispatcher=router,
        )
        service.create_plan(
            {
                "schedule_id": "remote-plan",
                "name": "协调端唯一计划",
                "enabled": True,
                "timezone_id": "Asia/Shanghai",
                "trigger": {"type": "once", "local_datetime": "2026-09-01T08:01:00"},
                "misfire_policy": "skip",
                "max_lateness_seconds": 0,
                "overlap_policy": "skip",
                "dispatch_mode": "simultaneous",
                "entries": [
                    {
                        "entry_id": "remote-entry",
                        "host_id": target.identity.host_id,
                        "instance_id": "instance",
                        "product_id": "product",
                        "profile_id": "profile",
                    }
                ],
                "created_by": "coordinator-user",
            }
        )
        clock.advance(minutes=1)
        occurrence = service.process_due()[0]
        dispatch = service.list_dispatches(
            occurrence_id=occurrence["occurrence_id"]
        )[0]
        assert dispatch["status"] == "accepted"
        assert dispatch["run_id"]
        assert len(launches) == 2
        launch_count = len(launches)
        with pytest.raises(LanControlError) as ordinary_message:
            coordinator.secure_request(
                target.identity.host_id,
                "message.offer",
                {"dispatch_id": "must-not-run"},
            )
        assert ordinary_message.value.error_id != "schedule.execution_start_failed"
        assert len(launches) == launch_count
    finally:
        coordinator.stop()
        target.stop()


def test_true_two_process_socket_message_e2e_and_private_addresses_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_create_connection = socket.create_connection

    def guarded(address: tuple[str, int], *args: Any, **kwargs: Any):
        parsed = ipaddress.ip_address(address[0])
        assert parsed.is_loopback or parsed.is_private
        return original_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded)
    process_context = multiprocessing.get_context("spawn")
    parent_pipe, child_pipe = process_context.Pipe()
    child = process_context.Process(
        target=_message_child,
        args=(str(tmp_path / "child"), child_pipe),
        name="easycode-lan-e2e-child",
    )
    child.start()
    control = _control(tmp_path / "parent-lan")
    runtime = MessageRuntimeV6(tmp_path / "parent.sqlite3", lan_control=control)
    sender = runtime.register_instance(
        "product", "父进程发送实例", endpoint_key="parent-sender"
    )
    try:
        assert parent_pipe.poll(10), "child listener did not start"
        ready = parent_pipe.recv()
        control.start()
        parent_pipe.send(("session",))
        assert parent_pipe.poll(5)
        offer = parent_pipe.recv()
        pending = control.begin_pairing(
            address="127.0.0.1",
            port=int(ready["port"]),
            code=offer["code"],
            session_id=offer["session_id"],
            permissions={"messages": True, "status": True},
        )
        parent_pipe.send(("confirm", pending["pending_id"]))
        assert parent_pipe.poll(5)
        parent_pipe.recv()
        control.complete_pairing(
            pending, expected_fingerprint=str(ready["fingerprint"])
        )
        control.refresh_peer_status(str(ready["host_id"]))
        batch = runtime.send(
            _context(sender),
            [ready["receiver"]["reference"]],
            "双进程消息",
            {"socket": "real"},
            ttl_ms=5_000,
        )
        parent_pipe.send(("receive", "双进程消息"))
        assert parent_pipe.poll(5)
        received = parent_pipe.recv()
        assert received["content"] == {"socket": "real"}
        assert runtime.wait_read(
            _context(sender), batch, timeout_ms=3_000
        )["condition_met"] is True
    finally:
        control.stop()
        if child.is_alive():
            parent_pipe.send(("stop",))
        child.join(timeout=10)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
        parent_pipe.close()
    assert child.exitcode == 0


def test_player_hub_lan_http_exposes_only_local_control_plane(tmp_path: Path) -> None:
    control = _control(tmp_path / "lan")
    hub = PlayerHubV6(tmp_path / "hub", lan_control=control)
    app = FastAPI()
    app.include_router(create_vnext_player_lan_router(hub))
    client = TestClient(app)
    try:
        started = client.post("/api/vnext/player-hub/lan/listener")
        assert started.status_code == 200
        assert started.json()["running"] is True
        offer = client.post(
            "/api/vnext/player-hub/lan/pairing-sessions",
            json={"ttl_ms": 60_000},
        )
        assert offer.status_code == 201
        assert len(offer.json()["code"].replace("-", "")) == 8
        assert '"kind":"easycode_pairing"' in offer.json()["qr_payload"]
        status = client.get("/api/vnext/player-hub/lan").json()
        assert status["cloud_relay"] == {
            "available": False,
            "state": "not_in_product_scope",
        }
        assert "cloud_devices" not in status
        stopped = client.delete("/api/vnext/player-hub/lan/listener")
        assert stopped.json() == {"ok": True, "state": "stopped"}
    finally:
        hub.shutdown()
