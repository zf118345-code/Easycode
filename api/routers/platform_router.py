from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

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
    async def save_schedule(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        store = _local_store(request, scope)
        try:
            return await run_in_threadpool(
                lambda: store.save_schedule(
                    payload.get('name') or '未命名计划',
                    payload.get('schedule_type') or 'daily',
                    payload.get('schedule_value') or '00:00',
                    payload.get('payload') or {},
                    enabled=bool(payload.get('enabled', True)),
                    schedule_id=payload.get('id'),
                )
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete('/api/platform/schedules/{schedule_id}')
    async def delete_schedule(schedule_id: str, request: Request, scope: str = 'ide'):
        return {'deleted': await run_in_threadpool(_local_store(request, scope).delete_schedule, schedule_id)}

    @router.post('/api/platform/messages')
    async def local_publish(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        store = _local_store(request, scope)
        return await run_in_threadpool(
            lambda: store.publish_message(
                payload.get('channel') or 'default', payload.get('payload'),
                sender=payload.get('sender') or '', ttl_seconds=int(payload.get('ttl_seconds') or 86400),
                message_id=payload.get('id'),
            )
        )

    @router.get('/api/platform/messages')
    async def list_local_messages(request: Request, channel: str | None = None, limit: int = 100, scope: str = 'ide'):
        return {'messages': await run_in_threadpool(_local_store(request, scope).list_messages, channel, limit)}

    @router.post('/api/platform/messages/claim')
    async def local_claim(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        store = _local_store(request, scope)
        messages = await run_in_threadpool(
            lambda: store.claim_messages(
                payload.get('channel') or 'default', payload.get('consumer') or 'default',
                limit=int(payload.get('limit') or 20), lease_seconds=int(payload.get('lease_seconds') or 30),
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/messages/{message_id}/ack')
    async def local_ack(message_id: str, request: Request, payload: dict = Body(...), scope: str = 'ide'):
        return {'acked': await run_in_threadpool(_local_store(request, scope).ack_message, message_id, payload.get('consumer') or 'default')}

    @router.post('/api/platform/leases/acquire')
    async def local_acquire(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        lease = await run_in_threadpool(
            _local_store(request, scope).acquire_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', int(payload.get('ttl_seconds') or 30),
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='资源正被其他实例占用')
        return lease

    @router.get('/api/platform/leases')
    async def list_local_leases(request: Request, scope: str = 'ide'):
        return {'leases': await run_in_threadpool(_local_store(request, scope).list_leases)}

    @router.post('/api/platform/leases/release')
    async def local_release(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        released = await run_in_threadpool(
            _local_store(request, scope).release_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', payload.get('token') or '',
        )
        return {'released': released}

    @router.post('/api/platform/leases/renew')
    async def local_renew(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        renewed = await run_in_threadpool(
            _local_store(request, scope).renew_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', payload.get('token') or '',
            int(payload.get('ttl_seconds') or 30),
        )
        return {'renewed': renewed}

    @router.post('/api/platform/remote/messages')
    async def remote_publish(request: Request, payload: dict = Body(...), scope: str = 'ide'):
        store = _local_store(request, scope)
        return await run_in_threadpool(
            lambda: platform_runtime_service.send_remote_message(
                store, payload.get('endpoint') or '', payload.get('token') or '',
                payload.get('channel') or 'default', payload.get('payload'),
                sender=payload.get('sender') or '', ttl_seconds=int(payload.get('ttl_seconds') or 86400),
            )
        )

    @router.post('/api/platform/remote/messages/claim')
    async def remote_claim_messages(payload: dict = Body(...)):
        messages = await run_in_threadpool(
            lambda: platform_runtime_service.claim_remote_messages(
                payload.get('endpoint') or '', payload.get('token') or '', payload.get('channel') or 'default',
                payload.get('consumer') or 'default', limit=int(payload.get('limit') or 20),
                lease_seconds=int(payload.get('lease_seconds') or 30),
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/remote/messages/{message_id}/ack')
    async def remote_ack_message(message_id: str, payload: dict = Body(...)):
        return {'acked': await run_in_threadpool(
            platform_runtime_service.ack_remote_message,
            payload.get('endpoint') or '', payload.get('token') or '', message_id, payload.get('consumer') or 'default',
        )}

    @router.post('/api/platform/remote/leases/acquire')
    async def remote_acquire_lease(payload: dict = Body(...)):
        lease = await run_in_threadpool(
            lambda: platform_runtime_service.acquire_remote_lease(
                payload.get('endpoint') or '', payload.get('token') or '', payload.get('resource_key') or '',
                payload.get('owner') or '', ttl_seconds=int(payload.get('ttl_seconds') or 30),
            )
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='远程资源正被其他实例占用')
        return lease

    @router.post('/api/platform/remote/leases/renew')
    async def remote_renew_lease(payload: dict = Body(...)):
        return {'renewed': await run_in_threadpool(
            lambda: platform_runtime_service.renew_remote_lease(
                payload.get('endpoint') or '', payload.get('token') or '', payload.get('resource_key') or '',
                payload.get('owner') or '', payload.get('lease_token') or '', ttl_seconds=int(payload.get('ttl_seconds') or 30),
            )
        )}

    @router.post('/api/platform/remote/leases/release')
    async def remote_release_lease(payload: dict = Body(...)):
        return {'released': await run_in_threadpool(
            platform_runtime_service.release_remote_lease,
            payload.get('endpoint') or '', payload.get('token') or '', payload.get('resource_key') or '',
            payload.get('owner') or '', payload.get('lease_token') or '',
        )}

    @router.get('/api/platform/outbox')
    async def outbox_status(request: Request, scope: str = 'ide'):
        return await run_in_threadpool(_local_store(request, scope).outbox_status)

    # Coordinator endpoints are safe to expose on a LAN only when a secret is
    # configured.  They deliberately do not accept workspace headers/paths.
    @router.post('/api/platform/coord/messages')
    async def coord_publish(payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        store = platform_runtime_service.coordinator_store()
        return await run_in_threadpool(
            lambda: store.publish_message(
                payload.get('channel') or 'default', payload.get('payload'),
                sender=payload.get('sender') or '', ttl_seconds=int(payload.get('ttl_seconds') or 86400),
                message_id=payload.get('id'),
            )
        )

    @router.post('/api/platform/coord/messages/claim')
    async def coord_claim(payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        messages = await run_in_threadpool(
            lambda: platform_runtime_service.coordinator_store().claim_messages(
                payload.get('channel') or 'default', payload.get('consumer') or 'default',
                limit=int(payload.get('limit') or 20), lease_seconds=int(payload.get('lease_seconds') or 30),
            )
        )
        return {'messages': messages}

    @router.post('/api/platform/coord/messages/{message_id}/ack')
    async def coord_ack(message_id: str, payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        acked = await run_in_threadpool(platform_runtime_service.coordinator_store().ack_message, message_id, payload.get('consumer') or 'default')
        return {'acked': acked}

    @router.post('/api/platform/coord/leases/acquire')
    async def coord_acquire(payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        lease = await run_in_threadpool(
            platform_runtime_service.coordinator_store().acquire_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', int(payload.get('ttl_seconds') or 30),
        )
        if lease is None:
            raise HTTPException(status_code=409, detail='资源正被其他实例占用')
        return lease

    @router.post('/api/platform/coord/leases/release')
    async def coord_release(payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        return {'released': await run_in_threadpool(
            platform_runtime_service.coordinator_store().release_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', payload.get('token') or '',
        )}

    @router.post('/api/platform/coord/leases/renew')
    async def coord_renew(payload: dict = Body(...), x_easycode_token: str | None = Header(default=None)):
        _require_coordinator_token(x_easycode_token)
        return {'renewed': await run_in_threadpool(
            platform_runtime_service.coordinator_store().renew_lease,
            payload.get('resource_key') or '', payload.get('owner') or '', payload.get('token') or '',
            int(payload.get('ttl_seconds') or 30),
        )}

    return router
