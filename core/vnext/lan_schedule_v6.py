"""Authenticated LAN adapters for the v6 coordinator-owned schedule model."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .lan_control_v6 import LanControlError, LanControlPlaneV6
from .schedule_v6 import (
    DispatchAcceptance,
    LocalDispatchPort,
    LocalDispatchRequest,
    ScheduleError,
    ScheduleReferenceResolver,
    SQLiteLocalDispatchGateway,
)


_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _stable(value: Any, label: str) -> str:
    clean = str(value or "").strip()
    if not _STABLE_ID.fullmatch(clean):
        raise ScheduleError(
            f"{label}不是有效稳定标识",
            error_id="schedule.identity_invalid",
        )
    return clean


def _schedule_error(exc: LanControlError) -> ScheduleError:
    if exc.error_id in {
        "lan.peer_unknown",
        "lan.permission_remote_start_denied",
        "lan.remote_permission_remote_start_denied",
        "lan.remote_product_denied",
        "lan.remote_instance_denied",
    }:
        return ScheduleError(
            str(exc),
            error_id="schedule.remote_dispatch_denied",
            transient=False,
            action=exc.action or "review_device_permissions",
        )
    return ScheduleError(
        str(exc),
        error_id=(
            "schedule.remote_host_unreachable"
            if exc.error_id in {"lan.device_unreachable", "lan.connection_interrupted"}
            else "schedule.remote_dispatch_failed"
        ),
        transient=bool(exc.transient),
        action=exc.action or "retry",
    )


class LanScheduleReferenceResolverV6(ScheduleReferenceResolver):
    """Resolve local registry records or pinned remote catalog records."""

    def __init__(
        self,
        local: ScheduleReferenceResolver,
        local_host_id: str,
        control: LanControlPlaneV6,
    ) -> None:
        self.local = local
        self.local_host_id = str(local_host_id)
        self.control = control

    def resolve(self, entry: Mapping[str, Any]) -> Mapping[str, Any]:
        host_id = str(entry.get("host_id") or "")
        if host_id == self.local_host_id:
            return dict(self.local.resolve(entry))
        try:
            peer = self.control.directory.peer(host_id)
            grants = peer["remote_permissions"]
            if not bool(grants.get("remote_start")):
                raise LanControlError(
                    "远端设备没有授予远程启动权限",
                    error_id="lan.remote_permission_remote_start_denied",
                    action="ask_remote_to_grant_permission",
                )
            product_id = str(entry.get("product_id") or "")
            instance_id = str(entry.get("instance_id") or "")
            products = set(grants.get("allowed_products") or [])
            instances = set(grants.get("allowed_instances") or [])
            if products and product_id not in products:
                raise LanControlError(
                    "产品不在远端启动授权范围",
                    error_id="lan.remote_product_denied",
                )
            if instances and instance_id not in instances:
                raise LanControlError(
                    "实例不在远端启动授权范围",
                    error_id="lan.remote_instance_denied",
                )
            remote = self.control.directory.remote_instance(
                product_id, host_id, instance_id
            )
        except LanControlError as exc:
            raise _schedule_error(exc) from exc
        if str(remote.get("product_id") or "") != str(entry.get("product_id") or ""):
            raise ScheduleError(
                "远端实例与产品身份不一致",
                error_id="schedule.reference_unknown",
            )
        profile_id = str(entry.get("profile_id") or "")
        profiles = [
            dict(item)
            for item in (remote.get("profiles") or [])
            if isinstance(item, Mapping)
        ]
        profile = next(
            (item for item in profiles if str(item.get("profile_id") or "") == profile_id),
            None,
        )
        if profile is None:
            raise ScheduleError(
                "远端运行方案不存在；请刷新设备状态",
                error_id="schedule.reference_unknown",
                action="refresh_device_status",
            )
        return {
            "dispatch_scope": "remote",
            "host_name": str(peer.get("device_name") or host_id),
            "instance_name": str(remote.get("display_name") or instance_id),
            "product_name": str(remote.get("product_name") or remote["product_id"]),
            "profile_name": str(profile.get("name") or profile_id),
            "release_id": str(profile.get("release_id") or remote.get("release_id") or ""),
        }


class LanDispatchRouterV6(LocalDispatchPort):
    """Route immutable dispatches locally or to one explicitly paired host."""

    def __init__(
        self,
        local_host_id: str,
        local: LocalDispatchPort,
        control: LanControlPlaneV6,
    ) -> None:
        self.local_host_id = str(local_host_id)
        self.local = local
        self.control = control

    def accept(self, request: LocalDispatchRequest) -> DispatchAcceptance:
        if request.host_id == self.local_host_id:
            return self.local.accept(request)
        payload = request.as_dict()
        # Observation time is deliberately excluded from the remote command
        # identity so ACK-loss retries keep the exact same semantic payload.
        payload.pop("requested_at", None)
        try:
            result = self.control.secure_request(
                request.host_id,
                "dispatch.start",
                payload,
                request_id=f"dispatch_{request.dispatch_id}",
                ttl_ms=30_000,
            )
        except LanControlError as exc:
            raise _schedule_error(exc) from exc
        if (
            str(result.get("dispatch_id") or "") != request.dispatch_id
            or not str(result.get("run_id") or "")
        ):
            raise ScheduleError(
                "远端接纳返回了不匹配的派发身份",
                error_id="schedule.execution_identity_mismatch",
            )
        return DispatchAcceptance(
            request.dispatch_id,
            str(result["run_id"]),
            str(result.get("status") or "accepted"),
        )


class LanScheduleInboundV6:
    """Target-side privileged command boundary; it never owns the plan."""

    def __init__(
        self,
        control: LanControlPlaneV6,
        gateway: SQLiteLocalDispatchGateway,
    ) -> None:
        self.control = control
        self.gateway = gateway
        control.register_handler("dispatch.start", self._start)
        control.register_handler("dispatch.status", self._status)

    @staticmethod
    def _lan_failure(exc: ScheduleError) -> LanControlError:
        return LanControlError(
            str(exc),
            error_id=exc.error_id,
            transient=exc.transient,
            action=exc.action,
        )

    def _start(self, _peer: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            host_id = _stable(payload.get("host_id"), "主机 ID")
            if host_id != self.control.identity.host_id:
                raise ScheduleError(
                    "远程启动命令不是发给当前设备",
                    error_id="schedule.reference_unknown",
                )
            request = LocalDispatchRequest(
                dispatch_id=_stable(payload.get("dispatch_id"), "派发 ID"),
                occurrence_id=_stable(payload.get("occurrence_id"), "发生 ID"),
                schedule_id=_stable(payload.get("schedule_id"), "计划 ID"),
                schedule_revision=int(payload.get("schedule_revision") or 0),
                entry_id=_stable(payload.get("entry_id"), "条目 ID"),
                host_id=host_id,
                instance_id=_stable(payload.get("instance_id"), "实例 ID"),
                product_id=_stable(payload.get("product_id"), "产品 ID"),
                profile_id=_stable(payload.get("profile_id"), "运行方案 ID"),
                requested_at="remote_authenticated",
            )
            if request.schedule_revision < 1:
                raise ScheduleError(
                    "计划修订号无效", error_id="schedule.reference_invalid"
                )
            accepted = self.gateway.accept(request)
            return {
                "dispatch_id": accepted.dispatch_id,
                "run_id": accepted.run_id,
                "status": accepted.status,
            }
        except (ScheduleError, TypeError, ValueError) as exc:
            if not isinstance(exc, ScheduleError):
                exc = ScheduleError(
                    "远程派发正文无效", error_id="schedule.reference_invalid"
                )
            raise self._lan_failure(exc) from exc

    def _status(self, _peer: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.gateway.get_admission(
                _stable(payload.get("dispatch_id"), "派发 ID")
            )
        except ScheduleError as exc:
            raise self._lan_failure(exc) from exc


__all__ = [
    "LanDispatchRouterV6",
    "LanScheduleInboundV6",
    "LanScheduleReferenceResolverV6",
]
