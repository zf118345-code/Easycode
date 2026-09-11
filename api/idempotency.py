"""FastAPI adapter for the infrastructure-neutral idempotency ledger."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from api.errors import failure_detail
from core.services.idempotency_service import (
    IdempotencyConflict,
    IdempotencyExecutionFailed,
    IdempotencyWaitTimeout,
    idempotency_ledger,
)


async def execute_idempotent(
    key: str,
    operation: str,
    fingerprint_payload: Any,
    producer: Callable[[], Awaitable[Any]],
    *,
    timeout: float = 600,
) -> Any:
    """Run an async producer once for each operation/key/fingerprint tuple."""

    if not str(key or '').strip():
        return await producer()
    try:
        claim = idempotency_ledger.claim(key, operation, fingerprint_payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=failure_detail('invalid_idempotency_key', str(exc), action='fix_request'),
        ) from exc
    except IdempotencyConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=failure_detail(
                'idempotency_conflict', str(exc), action='fix_request',
                recovery_message='为新的操作生成新的 Idempotency-Key',
            ),
        ) from exc

    if claim.role == 'cached':
        return claim.cached_result
    if claim.role == 'wait':
        try:
            return await run_in_threadpool(idempotency_ledger.wait, claim, timeout)
        except IdempotencyExecutionFailed as exc:
            raise exc.original from exc
        except IdempotencyWaitTimeout as exc:
            raise HTTPException(
                status_code=504,
                detail=failure_detail('idempotency_wait_timeout', str(exc), action='retry'),
            ) from exc

    try:
        result = await producer()
    except BaseException as exc:
        idempotency_ledger.fail(claim, exc)
        raise
    idempotency_ledger.complete(claim, result)
    return result
