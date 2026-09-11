from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from api.contracts.platform import (
    LeaseAcquireRequest,
    LeaseMutationRequest,
    MessageAckRequest,
    MessageClaimRequest,
    MessagePublishRequest,
    RemoteLeaseAcquireRequest,
    RemoteLeaseMutationRequest,
    RemoteMessageAckRequest,
    RemoteMessageClaimRequest,
    RemoteMessagePublishRequest,
    ScheduleSaveRequest,
)
from api.workspace_context import request_project_path
from core.services.platform_runtime_service import platform_runtime_service


def _local_store(request: Request, scope: str):
    if scope == 'player':
        from core.services.player_service import PlayerService

        return platform_runtime_service.register_player(PlayerService._runtime_root())
    return platform_runtime_service.register_project(request_project_path(request, writable=True))


def _require_coordinator_token(value: str | None):
    expected = str(os.environ.get('EASYCODE_COORDINATOR_TOKEN') or '')
    if not expected:
        raise HTTPException(status_code=503, detail='协调服务未配置 EASYCODE_COORDINATOR_TOKEN')
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail='协调服务令牌无效')


def create_platform_router():
    router = APIRouter(tags=['平台运行时'])

    @router.get('/api/platform/state/{key}')
    async def get_state(key: str, request: Request, namespace: str = 'default', scope: str = 'ide'):
        store = _local_store(request, scope)
        return {'key': key, 'namespace': namespace, 'value': await run_in_threadpool(store.get_state, key, namespace)}

    @router.get('/api/platform/overview')
    async def overview(request: Request, scope: str = 'ide'):
        return await run_in_threadpool(_local_store(request, scope).overview)

    @router.get('/api/platform/state-values')
    async def list_states(request: Request, namespace: str | None = None, scope: str = 'ide'):
        return {'states': await run_in_threadpool(_local_store(request, scope).list_states, namespace)}

    @router.put('/api/platform/state/{key}')
    async def set_state(key: str, request: Request, payload=Body(default=None), namespace: str = 'default', scope: str = 'ide'):
        return await run_in_threadpool(_local_store(request, scope).set_state, key, payload, namespace)

    @router.delete('/api/platform/state/{key}')
    async def delete_state(key: str, request: Request, namespace: str = 'default', scope: str = 'ide'):
        return {'deleted': await run_in_threadpool(_local_store(request, scope).delete_state, key, namespace)}

    @router.get('/api/platform/schedules')
    async def list_schedules(request: Request, scope: str = 'ide'):
        return {'schedules': await run_in_threadpool(_local_store(request, scope).list_schedules)}

    @router.post('/api/platform/schedules')
    async def save_schedule(request: Request, payload: ScheduleSaveRequest, scope: str = 'ide'):
        store = _local_store(request, scope)
        try:
            return await run_in_threadpool(
                lambda: store.save_schedule(
                    payload.name,
                    payload.schedule_type,
                    payload.schedule_value,
                    payload.payload,
                    enabled=payload.enabled,
                    schedule_id=payload.id or None,
                )
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete('/api/platform/schedules/{schedule_id}')
    async def delete_schedule(schedule_id: str, request: Request, scope: str = 'ide'):
        return {'deleted': await run_in_threadpool(_local_store(request, scope).delete_schedule, schedule_id)}

    @router.post('/api/platform/messages')
    async def local_publish(request: Request, payload: MessagePublishRequest, scope: str = 'ide'):
        store = _local_store(request, scope)
        return await run_in_threadpool(
            lambda: store.publish_message(
                payload.channel, payload.payload,
                sender=payload.sender, ttl_seconds=payload.ttl_seconds,
                message_id=payload.id,
            )
        )

    @router.get('/api/platform/messages')
    async def list_local_messages(request: Request, channel: str | None = None, limit: int = 100, scope: str = 'ide'):
        return {'messages': await run_in_threadpool(_local_store(request, scope).list_messages, channel, limit)}

    @router.post('/api/platform/messages/claim')
    async def local_claim(request: Request, payload: MessageClaimRequest, scope: str = 'ide'):
        store = _local_store(request, scope)
        messages = await run_in_threadpool(
            lambda: store.claim_messages(
                payload.channel, payload.consumer,
                limit=payload.limit, lease_seconds=payload.lease_seconds,
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/messages/{message_id}/ack')
    async def local_ack(message_id: str, request: Request, payload: MessageAckRequest, scope: str = 'ide'):
        return {'acked': await run_in_threadpool(_local_store(request, scope).ack_message, message_id, payload.consumer)}

    @router.post('/api/platform/leases/acquire')
    async def local_acquire(request: Request, payload: LeaseAcquireRequest, scope: str = 'ide'):
        lease = await run_in_threadpool(
            _local_store(request, scope).acquire_lease,
            payload.resource_key, payload.owner, payload.ttl_seconds,
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='资源正被其他实例占用')
        return lease

    @router.get('/api/platform/leases')
    async def list_local_leases(request: Request, scope: str = 'ide'):
        return {'leases': await run_in_threadpool(_local_store(request, scope).list_leases)}

    @router.post('/api/platform/leases/release')
    async def local_release(request: Request, payload: LeaseMutationRequest, scope: str = 'ide'):
        released = await run_in_threadpool(
            _local_store(request, scope).release_lease,
            payload.resource_key, payload.owner, payload.token,
        )
        return {'released': released}

    @router.post('/api/platform/leases/renew')
    async def local_renew(request: Request, payload: LeaseMutationRequest, scope: str = 'ide'):
        renewed = await run_in_threadpool(
            _local_store(request, scope).renew_lease,
            payload.resource_key, payload.owner, payload.token,
            payload.ttl_seconds,
        )
        return {'renewed': renewed}

    @router.post('/api/platform/remote/messages')
    async def remote_publish(request: Request, payload: RemoteMessagePublishRequest, scope: str = 'ide'):
        store = _local_store(request, scope)
        return await run_in_threadpool(
            lambda: platform_runtime_service.send_remote_message(
                store, payload.endpoint, payload.token,
                payload.channel, payload.payload,
                sender=payload.sender, ttl_seconds=payload.ttl_seconds,
            )
        )

    @router.post('/api/platform/remote/messages/claim')
    async def remote_claim_messages(payload: RemoteMessageClaimRequest):
        messages = await run_in_threadpool(
            lambda: platform_runtime_service.claim_remote_messages(
                payload.endpoint, payload.token, payload.channel,
                payload.consumer, limit=payload.limit,
                lease_seconds=payload.lease_seconds,
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/remote/messages/{message_id}/ack')
    async def remote_ack_message(message_id: str, payload: RemoteMessageAckRequest):
        return {'acked': await run_in_threadpool(
            platform_runtime_service.ack_remote_message,
            payload.endpoint, payload.token, message_id, payload.consumer,
        )}

    @router.post('/api/platform/remote/leases/acquire')
    async def remote_acquire_lease(payload: RemoteLeaseAcquireRequest):
        lease = await run_in_threadpool(
            lambda: platform_runtime_service.acquire_remote_lease(
                payload.endpoint, payload.token, payload.resource_key,
                payload.owner, ttl_seconds=payload.ttl_seconds,
            )
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='远程资源正被其他实例占用')
        return lease

    @router.post('/api/platform/remote/leases/renew')
    async def remote_renew_lease(payload: RemoteLeaseMutationRequest):
        return {'renewed': await run_in_threadpool(
            lambda: platform_runtime_service.renew_remote_lease(
                payload.endpoint, payload.token, payload.resource_key,
                payload.owner, payload.lease_token, ttl_seconds=payload.ttl_seconds,
            )
        )}

    @router.post('/api/platform/remote/leases/release')
    async def remote_release_lease(payload: RemoteLeaseMutationRequest):
        return {'released': await run_in_threadpool(
            platform_runtime_service.release_remote_lease,
            payload.endpoint, payload.token, payload.resource_key,
            payload.owner, payload.lease_token,
        )}

    @router.get('/api/platform/outbox')
    async def outbox_status(request: Request, scope: str = 'ide'):
        return await run_in_threadpool(_local_store(request, scope).outbox_status)

    # Coordinator endpoints are safe to expose on a LAN only when a secret is
    # configured.  They deliberately do not accept workspace headers/paths.
    @router.post('/api/platform/coord/messages')
    async def coord_publish(
        payload: MessagePublishRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        store = platform_runtime_service.coordinator_store()
        return await run_in_threadpool(
            lambda: store.publish_message(
                payload.channel, payload.payload,
                sender=payload.sender, ttl_seconds=payload.ttl_seconds,
                message_id=payload.id,
            )
        )

    @router.post('/api/platform/coord/messages/claim')
    async def coord_claim(
        payload: MessageClaimRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        messages = await run_in_threadpool(
            lambda: platform_runtime_service.coordinator_store().claim_messages(
                payload.channel, payload.consumer,
                limit=payload.limit, lease_seconds=payload.lease_seconds,
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/coord/messages/{message_id}/ack')
    async def coord_ack(
        message_id: str,
        payload: MessageAckRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        acked = await run_in_threadpool(
            platform_runtime_service.coordinator_store().ack_message,
            message_id,
            payload.consumer,
        )
        return {'acked': acked}

    @router.post('/api/platform/coord/leases/acquire')
    async def coord_acquire(
        payload: LeaseAcquireRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        lease = await run_in_threadpool(
            platform_runtime_service.coordinator_store().acquire_lease,
            payload.resource_key, payload.owner, payload.ttl_seconds,
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='资源正被其他实例占用')
        return lease

    @router.post('/api/platform/coord/leases/release')
    async def coord_release(
        payload: LeaseMutationRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        return {'released': await run_in_threadpool(
            platform_runtime_service.coordinator_store().release_lease,
            payload.resource_key, payload.owner, payload.token,
        )}

    @router.post('/api/platform/coord/leases/renew')
    async def coord_renew(
        payload: LeaseMutationRequest,
        x_easycode_token: str | None = Header(default=None),
    ):
        _require_coordinator_token(x_easycode_token)
        return {'renewed': await run_in_threadpool(
            platform_runtime_service.coordinator_store().renew_lease,
            payload.resource_key, payload.owner, payload.token,
            payload.ttl_seconds,
        )}

    return router
