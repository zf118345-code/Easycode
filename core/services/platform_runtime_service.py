from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from core.services.platform_store import PlatformStore

logger = logging.getLogger(__name__)


class _ThreadBackgroundTasks:
    """BackgroundTasks-compatible launcher used by the persistent scheduler."""

    def add_task(self, function, *args, **kwargs):
        threading.Thread(target=function, args=args, kwargs=kwargs, daemon=True).start()


class PlatformRuntimeService:
    """Lifecycle manager for schedules, reliable outbox and runtime stores."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stores: dict[str, dict[str, Any]] = {}
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._owner = f'{os.getpid()}-{uuid.uuid4().hex[:8]}'

    def _start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name='easycode-platform-runtime', daemon=True)
            self._thread.start()

    def register_project(self, project_path: str) -> PlatformStore:
        root = str(Path(project_path).resolve())
        path = str(Path(root) / '.easycode' / 'runtime' / 'platform.db')
        return self._register(path, 'ide', root)

    def register_player(self, runtime_root: str) -> PlatformStore:
        root = str(Path(runtime_root).resolve())
        return self._register(str(Path(root) / 'platform.db'), 'player', root)

    def coordinator_store(self) -> PlatformStore:
        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        return self._register(str(Path(base) / 'EasyCode' / 'Coordinator' / 'coordinator.db'), 'coordinator', '')

    def _register(self, path: str, kind: str, root: str) -> PlatformStore:
        key = str(Path(path).resolve())
        with self._lock:
            if key not in self._stores:
                self._stores[key] = {'store': PlatformStore(key), 'kind': kind, 'root': root}
            store = self._stores[key]['store']
        self._start()
        self._wake.set()
        return store

    @staticmethod
    def _post_json(url: str, token: str, payload: Any, timeout: float = 5.0) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(str(url or '').strip())
        if parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('远程协调器地址必须是有效的 HTTP 或 HTTPS URL')
        if parsed.username or parsed.password:
            raise ValueError('远程协调器地址不能包含用户名或密码')
        request = urllib.request.Request(  # noqa: S310 - scheme validated above
            parsed.geturl(),
            data=json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'X-EasyCode-Token': str(token or '')},
            method='POST',
        )
        # urlsplit above rejects every scheme except HTTP(S).
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310
            raw = response.read(2 * 1024 * 1024)
        return json.loads(raw.decode('utf-8')) if raw else {'status': 'success'}

    def send_remote_message(
        self,
        store: PlatformStore,
        endpoint: str,
        token: str,
        channel: str,
        payload: Any,
        *,
        sender: str = '',
        ttl_seconds: int = 86400,
    ) -> dict[str, Any]:
        # The client owns the message id so that an ambiguous network failure
        # (the coordinator committed the request but the response was lost) can
        # be retried from the outbox without publishing the same command twice.
        message_id = str(uuid.uuid4())
        body = {
            'id': message_id,
            'channel': channel,
            'payload': payload,
            'sender': sender,
            'ttl_seconds': ttl_seconds,
        }
        url = str(endpoint).rstrip('/') + '/api/platform/coord/messages'
        try:
            result = self._post_json(url, token, body)
            return {'success': True, 'queued': False, 'message_id': message_id, 'result': result}
        except (OSError, ValueError, urllib.error.URLError) as exc:
            queued = store.enqueue_outbox(str(endpoint).rstrip('/'), token, 'message.publish', body)
            self._wake.set()
            return {
                'success': True,
                'queued': True,
                'message_id': message_id,
                'outbox_id': queued['id'],
                'message': str(exc),
            }

    def claim_remote_messages(
        self,
        endpoint: str,
        token: str,
        channel: str,
        consumer: str,
        *,
        limit: int = 20,
        lease_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        result = self._post_json(
            str(endpoint).rstrip('/') + '/api/platform/coord/messages/claim', token,
            {
                'channel': channel, 'consumer': consumer,
                'limit': max(1, min(500, int(limit))),
                'lease_seconds': max(1, int(lease_seconds)),
            },
        )
        return list(result.get('messages') or [])

    def ack_remote_message(self, endpoint: str, token: str, message_id: str, consumer: str) -> bool:
        result = self._post_json(
            str(endpoint).rstrip('/') + f'/api/platform/coord/messages/{message_id}/ack',
            token, {'consumer': consumer},
        )
        return bool(result.get('acked'))

    def acquire_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, *, ttl_seconds: int = 30,
    ) -> dict[str, Any] | None:
        try:
            return self._post_json(
                str(endpoint).rstrip('/') + '/api/platform/coord/leases/acquire', token,
                {'resource_key': resource_key, 'owner': owner, 'ttl_seconds': max(1, int(ttl_seconds))},
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                return None
            raise

    def renew_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, lease_token: str,
        *, ttl_seconds: int = 30,
    ) -> bool:
        result = self._post_json(
            str(endpoint).rstrip('/') + '/api/platform/coord/leases/renew', token,
            {
                'resource_key': resource_key, 'owner': owner, 'token': lease_token,
                'ttl_seconds': max(1, int(ttl_seconds)),
            },
        )
        return bool(result.get('renewed'))

    def release_remote_lease(
        self, endpoint: str, token: str, resource_key: str, owner: str, lease_token: str,
    ) -> bool:
        result = self._post_json(
            str(endpoint).rstrip('/') + '/api/platform/coord/leases/release', token,
            {'resource_key': resource_key, 'owner': owner, 'token': lease_token},
        )
        return bool(result.get('released'))

    def _dispatch_schedule(self, meta: dict[str, Any], schedule: dict[str, Any]) -> tuple[bool, str]:
        payload = schedule.get('payload') or {}
        try:
            if meta['kind'] == 'ide':
                from core.services.blueprint_service import BlueprintService
                from core.services.execution_service import ExecutionService

                project_path = meta['root']
                task_id = str(payload.get('task_id') or '')
                node_id = str(payload.get('node_id') or '')
                if not task_id or not node_id:
                    return False, 'IDE 计划缺少 task_id 或 node_id'
                blueprint = BlueprintService.load_blueprint(project_path)
                result = ExecutionService.run_task(
                    project_path, task_id, node_id, blueprint, _ThreadBackgroundTasks(),
                    persist_blueprint=False,
                )
                return True, str(result.get('execution_id') or 'started')
            if meta['kind'] == 'player':
                from core.services.player_service import PlayerService

                profile_name = str(payload.get('profile_name') or '').strip()
                instance_id = str(payload.get('instance_id') or 'instance-1')
                if profile_name:
                    PlayerService.apply_profile(profile_name, instance_id)
                result = PlayerService.run_script(
                    _ThreadBackgroundTasks(),
                    instance_id=instance_id,
                    resume=bool(payload.get('resume', False)),
                )
                return True, str(result.get('execution_id') or 'started')
            return False, f'存储类型 {meta["kind"]} 不执行计划'
        except Exception as exc:
            return False, str(exc)

    def _process_store(self, meta: dict[str, Any]) -> None:
        store: PlatformStore = meta['store']
        for item in store.due_outbox(20):
            try:
                if item['operation'] != 'message.publish':
                    raise ValueError(f'未知离线操作: {item["operation"]}')
                self._post_json(
                    str(item['endpoint']).rstrip('/') + '/api/platform/coord/messages',
                    item['token'], item['payload'],
                )
                store.complete_outbox(item['id'])
            except Exception as exc:
                store.fail_outbox(item['id'], int(item['attempts']) + 1, str(exc))

        if meta['kind'] not in {'ide', 'player'}:
            return
        for schedule in store.claim_due_schedules(self._owner, limit=5, lease_seconds=60):
            success, message = self._dispatch_schedule(meta, schedule)
            store.complete_schedule(schedule['id'], self._owner, success=success, error='' if success else message)
            if not success:
                logger.warning('计划任务启动失败 [%s]: %s', schedule.get('name'), message)

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                stores = list(self._stores.values())
            for meta in stores:
                if self._stop.is_set():
                    break
                try:
                    self._process_store(meta)
                except Exception:
                    logger.exception('平台运行时维护失败: %s', meta.get('root') or meta['store'].path)
            self._wake.wait(1.0)
            self._wake.clear()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        with self._lock:
            self._thread = None


platform_runtime_service = PlatformRuntimeService()
