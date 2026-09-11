"""Loopback-only management API for the v6 Player LAN control plane.

This router is deliberately independent from the authoring and schedule-management
routers so a packaged Player can expose only the controls it actually owns.  The
HTTP server must remain bound to loopback; authenticated LAN traffic uses the
separate :mod:`core.vnext.lan_control_v6` socket transport.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from api.contracts.vnext_player import ApiErrorResponse
from api.contracts.vnext_schedule_hub import (
    LanDiscoveryRequest,
    LanPairBeginRequest,
    LanPairCompleteRequest,
    LanPairConfirmRequest,
    LanPairingSessionRequest,
    LanPermissionsRequest,
)
from api.errors import failure_detail
from core.vnext.lan_control_v6 import LanControlError
from core.vnext.schedule_hub_v6 import PlayerHubV6, get_player_hub_v6


def _translate_lan(exc: LanControlError) -> None:
    status = 503 if exc.transient else 404 if exc.error_id.endswith("_unknown") else 409
    if any(token in exc.error_id for token in ("invalid", "mismatch", "expired")):
        status = 422
    raise HTTPException(
        status_code=status,
        detail=failure_detail(
            exc.error_id,
            str(exc),
            retryable=exc.transient,
            action=exc.action,
        ),
    ) from exc


def create_vnext_player_lan_router(hub: PlayerHubV6 | None = None) -> APIRouter:
    """Create the packaged-Player-safe, loopback LAN-management router."""

    router = APIRouter(
        prefix="/api/vnext/player-hub/lan",
        tags=["EasyCode vNext Player LAN"],
        responses={
            code: {"model": ApiErrorResponse, "description": description}
            for code, description in (
                (404, "已配对设备或待确认配对不存在"),
                (409, "监听、权限、撤销或固定身份状态冲突"),
                (422, "配对码、二维码、地址、指纹或权限字段无效"),
                (503, "LAN 监听或目标设备暂时不可用"),
            )
        },
    )

    def current() -> PlayerHubV6:
        # OpenAPI generation must remain side-effect free.
        return hub if hub is not None else get_player_hub_v6()

    @router.get("")
    async def lan_status():
        return await run_in_threadpool(current().lan_control.status)

    @router.post("/listener")
    async def start_lan_listener():
        try:
            return await run_in_threadpool(current().lan_control.start)
        except LanControlError as exc:
            _translate_lan(exc)

    @router.delete("/listener")
    async def stop_lan_listener():
        await run_in_threadpool(current().lan_control.stop)
        return {"ok": True, "state": "stopped"}

    @router.post("/discovery")
    async def discover_lan(request: LanDiscoveryRequest):
        try:
            control = current().lan_control
            if not control.status()["running"]:
                await run_in_threadpool(control.start)
            return await run_in_threadpool(
                control.discover,
                timeout_seconds=request.timeout_seconds,
                port=request.port,
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.post("/pairing-sessions", status_code=201)
    async def create_pairing_session(request: LanPairingSessionRequest):
        try:
            control = current().lan_control
            if not control.status()["running"]:
                await run_in_threadpool(control.start)
            return await run_in_threadpool(
                control.create_pairing_session, request.ttl_ms
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.post("/pairing/begin")
    async def begin_pairing(request: LanPairBeginRequest):
        try:
            values: dict[str, object] = {}
            if request.qr_payload:
                parsed = json.loads(request.qr_payload)
                if not isinstance(parsed, dict) or parsed.get("kind") != "easycode_pairing":
                    raise ValueError("kind")
                values.update(parsed)
            if request.address:
                values["address"] = request.address
            if request.port is not None:
                values["port"] = request.port
            if request.code:
                values["code"] = request.code
            if request.session_id:
                values["session_id"] = request.session_id
            addresses = values.get("addresses")
            address = str(values.get("address") or "")
            if not address and isinstance(addresses, list) and addresses:
                address = str(addresses[0])
            if (
                not address
                or not values.get("port")
                or not values.get("code")
                or not values.get("session_id")
            ):
                raise ValueError("missing")
            control = current().lan_control
            if not control.status()["running"]:
                await run_in_threadpool(control.start)
            result = await run_in_threadpool(
                control.begin_pairing,
                address=address,
                port=int(values["port"]),
                code=str(values["code"]),
                session_id=str(values["session_id"]),
                permissions=request.permissions.model_dump(),
            )
            expected_fingerprint = str(values.get("fingerprint") or "")
            receiver = result.get("receiver") or {}
            if (
                expected_fingerprint
                and str(receiver.get("fingerprint") or "") != expected_fingerprint
            ):
                raise LanControlError(
                    "二维码固定指纹与实际应答设备不一致",
                    error_id="lan.fingerprint_mismatch",
                    action="cancel_pairing",
                )
            return result
        except (ValueError, json.JSONDecodeError):
            _translate_lan(
                LanControlError(
                    "二维码或手工配对字段无效",
                    error_id="lan.pairing_payload_invalid",
                    action="scan_or_enter_again",
                )
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.post("/pairing/complete")
    async def complete_pairing(request: LanPairCompleteRequest):
        try:
            return await run_in_threadpool(
                current().lan_control.complete_pairing,
                request.pairing,
                expected_fingerprint=request.expected_fingerprint,
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.post("/pairing-pending/{pending_id}/confirm")
    async def confirm_pairing(pending_id: str, request: LanPairConfirmRequest):
        try:
            return await run_in_threadpool(
                current().lan_control.directory.confirm_pairing,
                pending_id,
                request.permissions.model_dump(),
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.patch("/peers/{host_id}/permissions")
    async def set_lan_permissions(host_id: str, request: LanPermissionsRequest):
        try:
            return await run_in_threadpool(
                current().lan_control.directory.set_permissions,
                host_id,
                request.model_dump(),
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.delete("/peers/{host_id}")
    async def revoke_lan_peer(host_id: str):
        try:
            return await run_in_threadpool(
                current().lan_control.directory.revoke, host_id
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.post("/peers/{host_id}/refresh")
    async def refresh_lan_peer(host_id: str):
        try:
            return await run_in_threadpool(
                current().lan_control.refresh_peer_status, host_id
            )
        except LanControlError as exc:
            _translate_lan(exc)

    @router.get("/diagnostics")
    async def lan_diagnostics(limit: int = Query(default=500, ge=1, le=5000)):
        return await run_in_threadpool(
            current().lan_control.directory.diagnostics, limit=limit
        )

    return router
