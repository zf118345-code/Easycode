"""Terminal-only HTTP surface for signed v6 Player updates.

This module deliberately does not import workspace, Publisher, IDE update, or Feed
management services so the independently packaged Player cannot acquire authoring
routes by including its update controls.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.contracts.vnext_update import (
    PlayerUpdateCheckRequest,
    PlayerUpdateDomainRequest,
    PlayerUpdatePreferencesRequest,
    PlayerUpdateSafePointRequest,
)
from api.errors import failure_detail
from core.vnext.player_bundle import PlayerBundleError, vnext_player_bundle_manager


def _translate_player_update_error(exc: PlayerBundleError) -> None:
    raise HTTPException(
        status_code=409,
        detail=failure_detail(
            "player_update_operation_failed",
            str(exc),
            action="retry",
        ),
    ) from exc


def create_vnext_player_update_router(
    *,
    prefix: str = "/api/vnext/player/runtime",
) -> APIRouter:
    """Create only the update routes safe to expose from the standalone Player."""

    router = APIRouter(prefix=prefix, tags=["EasyCode vNext Player Updates"])

    @router.get("/updates")
    async def player_update_status():
        try:
            if not vnext_player_bundle_manager.available():
                vnext_player_bundle_manager.ensure_from_environment()
            return await run_in_threadpool(vnext_player_bundle_manager.update_status)
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.post("/updates/check")
    async def player_update_check(payload: PlayerUpdateCheckRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.check_update,
                payload.domain,
                policy_only=payload.policy_only,
            )
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.post("/updates/download")
    async def player_update_download(payload: PlayerUpdateDomainRequest):
        try:
            return await run_in_threadpool(vnext_player_bundle_manager.download_update, payload.domain)
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.post("/updates/apply")
    async def player_update_apply(payload: PlayerUpdateDomainRequest):
        try:
            return await run_in_threadpool(vnext_player_bundle_manager.apply_update, payload.domain)
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.put("/updates/preferences")
    async def player_update_preferences(payload: PlayerUpdatePreferencesRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.save_update_preferences,
                payload.domain,
                payload.preferences.model_dump(mode="python"),
            )
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.get("/updates/{domain}/group-code")
    async def player_update_group_code(domain: str):
        try:
            return await run_in_threadpool(vnext_player_bundle_manager.update_group_code, domain)
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.post("/updates/reset-group")
    async def player_update_reset_group(payload: PlayerUpdateDomainRequest):
        try:
            return await run_in_threadpool(vnext_player_bundle_manager.reset_update_group, payload.domain)
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    @router.put("/updates/safe-point")
    async def player_update_safe_point(payload: PlayerUpdateSafePointRequest):
        try:
            return await run_in_threadpool(
                vnext_player_bundle_manager.mark_update_safe_point,
                running_or_paused=payload.running_or_paused,
                uncommitted_draft=payload.uncommitted_draft,
            )
        except PlayerBundleError as exc:
            _translate_player_update_error(exc)

    return router


__all__ = ["create_vnext_player_update_router"]
