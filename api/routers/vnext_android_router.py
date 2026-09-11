from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from api.errors import failure_detail
from api.idempotency import execute_idempotent
from core.vnext.android_delivery_v6 import (
    AndroidDeliveryError,
    android_delivery_service_v6,
)


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AndroidBuildRequest(_StrictRequest):
    bundle_path: str = Field(min_length=1, max_length=4096)
    trust_root_path: str = Field(min_length=1, max_length=4096)
    variant: Literal['productionDebug', 'emulatorDebug', 'productionRelease'] = 'productionDebug'
    output_path: str | None = Field(default=None, max_length=4096)
    verify_reproducible: bool = False


class AndroidInstallRequest(_StrictRequest):
    serial: str = Field(min_length=1, max_length=128)
    apk_path: str = Field(min_length=1, max_length=4096)


class AndroidLaunchRequest(_StrictRequest):
    serial: str = Field(min_length=1, max_length=128)
    application_id: str = Field(min_length=1, max_length=255)


class AndroidPushBundleRequest(AndroidLaunchRequest):
    bundle_path: str = Field(min_length=1, max_length=4096)
    trust_root_path: str = Field(min_length=1, max_length=4096)


class AndroidLogsRequest(AndroidLaunchRequest):
    lines: int = Field(default=400, ge=1, le=5000)


def create_vnext_android_router() -> APIRouter:
    router = APIRouter(prefix='/api/vnext/android', tags=['EasyCode vNext Android'])

    def require_local(request: Request) -> None:
        host = request.client.host if request.client else ''
        if host not in {'127.0.0.1', '::1', 'localhost', 'testclient'}:
            raise HTTPException(
                status_code=403,
                detail=failure_detail(
                    'android_bridge_local_only',
                    'APK 构建和 ADB 控制只允许 IDE 本机调用',
                    action='use_local_ide',
                ),
            )

    def translate(exc: AndroidDeliveryError) -> None:
        status = 409 if exc.code in {
            'android.device_unavailable', 'android.build_not_reproducible',
        } else 422
        raise HTTPException(
            status_code=status,
            detail=failure_detail(
                exc.code,
                str(exc),
                action='fix_request' if status == 422 else 'retry',
                diagnostics=exc.diagnostics,
            ),
        ) from exc

    @router.get('/devices')
    async def devices(request: Request):
        require_local(request)
        try:
            return {'devices': await run_in_threadpool(android_delivery_service_v6.devices)}
        except AndroidDeliveryError as exc:
            translate(exc)

    @router.post('/build')
    async def build(
        request: Request,
        payload: AndroidBuildRequest,
        idempotency_key: Annotated[str, Header(alias='Idempotency-Key')] = '',
    ):
        require_local(request)

        async def produce():
            try:
                return await run_in_threadpool(
                    android_delivery_service_v6.build,
                    payload.bundle_path,
                    payload.trust_root_path,
                    variant=payload.variant,
                    output_path=payload.output_path,
                    verify_reproducible=payload.verify_reproducible,
                )
            except AndroidDeliveryError as exc:
                translate(exc)

        return await execute_idempotent(
            idempotency_key,
            'vnext.android.build',
            payload.model_dump(mode='json'),
            produce,
            timeout=3600,
        )

    @router.post('/install')
    async def install(
        request: Request,
        payload: AndroidInstallRequest,
        idempotency_key: Annotated[str, Header(alias='Idempotency-Key')] = '',
    ):
        require_local(request)

        async def produce():
            try:
                return await run_in_threadpool(
                    android_delivery_service_v6.install, payload.serial, payload.apk_path,
                )
            except AndroidDeliveryError as exc:
                translate(exc)

        return await execute_idempotent(
            idempotency_key, 'vnext.android.install', payload.model_dump(mode='json'), produce,
        )

    @router.post('/launch')
    async def launch(
        request: Request,
        payload: AndroidLaunchRequest,
        idempotency_key: Annotated[str, Header(alias='Idempotency-Key')] = '',
    ):
        require_local(request)

        async def produce():
            try:
                return await run_in_threadpool(
                    android_delivery_service_v6.launch, payload.serial, payload.application_id,
                )
            except AndroidDeliveryError as exc:
                translate(exc)

        return await execute_idempotent(
            idempotency_key, 'vnext.android.launch', payload.model_dump(mode='json'), produce,
        )

    @router.post('/push-bundle')
    async def push_bundle(
        request: Request,
        payload: AndroidPushBundleRequest,
        idempotency_key: Annotated[str, Header(alias='Idempotency-Key')] = '',
    ):
        require_local(request)

        async def produce():
            try:
                return await run_in_threadpool(
                    android_delivery_service_v6.push_bundle,
                    payload.serial,
                    payload.application_id,
                    payload.bundle_path,
                    payload.trust_root_path,
                )
            except AndroidDeliveryError as exc:
                translate(exc)

        return await execute_idempotent(
            idempotency_key, 'vnext.android.push_bundle', payload.model_dump(mode='json'), produce,
        )

    @router.post('/logs')
    async def logs(request: Request, payload: AndroidLogsRequest):
        require_local(request)
        try:
            return await run_in_threadpool(
                android_delivery_service_v6.logs,
                payload.serial,
                payload.application_id,
                lines=payload.lines,
            )
        except AndroidDeliveryError as exc:
            translate(exc)

    return router
