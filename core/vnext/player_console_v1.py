"""Native Windows Player console with one isolated worker per instance."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.services.process_lifecycle import terminate_process_tree

from .schedule_hub_v6 import PlayerHubV6, get_player_hub_v6
from .schedule_v6 import ScheduleError


_ACTIVE_RUN_STATES = frozenset({'queued', 'running', 'paused'})
_LOOPBACK_HOSTS = frozenset({'127.0.0.1', 'localhost', '::1'})


def _checked_console_origin(raw: str) -> str:
    parsed = urlparse(str(raw or '').strip())
    if parsed.scheme != 'http' or parsed.hostname not in _LOOPBACK_HOSTS or parsed.port is None:
        raise ScheduleError(
            'Player 控制台来源必须是带端口的本机 HTTP 地址',
            error_id='schedule.console_origin_invalid',
        )
    host = '127.0.0.1' if parsed.hostname in {'127.0.0.1', 'localhost'} else '[::1]'
    return f'http://{host}:{parsed.port}'


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        temporary.write_text(value, encoding='utf-8')
        for attempt in range(3):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 2:
                    break
                time.sleep(0.01 * (attempt + 1))
        # Windows antivirus/indexing can briefly open owner.pid without delete
        # sharing, which blocks replace but still permits an in-place lease
        # refresh. A partial read is harmless because worker lease age remains
        # authoritative during the short retry window.
        path.write_text(value, encoding='utf-8')
    finally:
        temporary.unlink(missing_ok=True)


def _tail_text(path: Path, *, limit: int) -> str | None:
    """Read a bounded UTF-8 tail without loading an unbounded process log."""

    try:
        size = path.stat().st_size
        with path.open('rb') as stream:
            if size > limit:
                stream.seek(-limit, os.SEEK_END)
            payload = stream.read(limit)
    except OSError:
        return None
    text = payload.decode('utf-8', errors='replace')
    if size > limit:
        first_newline = text.find('\n')
        if first_newline >= 0:
            text = text[first_newline + 1:]
        text = f'[前部已省略；仅保留最后 {limit} 字节]\n{text}'
    return text


def _default_controller_logs() -> Path:
    local = str(os.environ.get('LOCALAPPDATA') or '').strip()
    base = Path(local) if local else Path.home() / 'AppData' / 'Local'
    return (base / 'EasyCode' / 'Player' / 'logs').resolve()


def _terminate_adopted_worker(process_id: int) -> bool:
    """Terminate one descriptor-verified worker that was adopted after restart."""

    try:
        import psutil

        root = psutil.Process(int(process_id))
    except ImportError:
        return False
    except psutil.NoSuchProcess:
        return True
    except (psutil.AccessDenied, ValueError):
        return False
    processes = root.children(recursive=True) + [root]
    for process in reversed(processes):
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(processes, timeout=1.5)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(alive, timeout=1.0)
    return not alive


def _request_json(
    origin: str,
    path: str,
    *,
    method: str = 'GET',
    timeout: float = 2.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f'{origin}{path}',
        method=method,
        headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
        data=b'{}' if method not in {'GET', 'HEAD'} else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback-only origin is validated
            payload = json.loads(response.read().decode('utf-8'))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ScheduleError(
            '无法连接该 Player 实例工作进程',
            error_id='schedule.instance_worker_unreachable',
            action='restart_instance_worker',
            transient=True,
        ) from exc
    if not isinstance(payload, dict):
        raise ScheduleError(
            'Player 实例工作进程返回了无效状态',
            error_id='schedule.instance_worker_invalid_response',
            action='restart_instance_worker',
        )
    return payload


@dataclass(slots=True)
class _Worker:
    instance_id: str
    descriptor_path: Path
    owner_path: Path
    stop_path: Path
    origin_path: Path
    process_id: int
    origin: str
    process: subprocess.Popen | None = None


class PlayerConsoleV1:
    """Own visible console state while preserving per-instance failure domains."""

    def __init__(self, hub: PlayerHubV6 | None = None, *, startup_timeout: float = 15.0) -> None:
        self.hub = hub if hub is not None else get_player_hub_v6()
        self.startup_timeout = max(1.0, float(startup_timeout))
        self._lock = threading.RLock()
        self._workers: dict[str, _Worker] = {}
        self._connection_locks: dict[str, threading.Lock] = {}

    @staticmethod
    def _paths(instance: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
        root = Path(str(instance['data_root'])).resolve() / 'console'
        return (
            root / 'worker.json',
            root / 'owner.pid',
            root / 'stop.request',
            root / 'console-origin.txt',
        )

    @staticmethod
    def _execution_status(state: dict[str, Any]) -> str:
        execution = state.get('execution') if isinstance(state.get('execution'), dict) else {}
        return str(execution.get('status') or '')

    def _worker_from_descriptor(self, instance: dict[str, Any]) -> _Worker | None:
        descriptor_path, owner_path, stop_path, origin_path = self._paths(instance)
        descriptor = _read_json(descriptor_path)
        if not descriptor:
            return None
        if str(descriptor.get('instance_id') or '') != str(instance['instance_id']):
            return None
        try:
            process_id = int(descriptor.get('process_id') or 0)
            port = int(descriptor.get('port') or 0)
        except (TypeError, ValueError):
            return None
        if process_id <= 0 or not 1 <= port <= 65535:
            return None
        worker = _Worker(
            instance_id=str(instance['instance_id']),
            descriptor_path=descriptor_path,
            owner_path=owner_path,
            stop_path=stop_path,
            origin_path=origin_path,
            process_id=process_id,
            origin=f'http://127.0.0.1:{port}',
        )
        try:
            state = _request_json(worker.origin, '/api/vnext/player/runtime/state', timeout=0.8)
        except ScheduleError:
            return None
        if str(state.get('instance_id') or '') != worker.instance_id:
            return None
        return worker

    @staticmethod
    def _frame_url(worker: _Worker) -> str:
        return f'{worker.origin}/player.html?embedded=1'

    def _adopt(self, worker: _Worker, console_origin: str | None = None) -> None:
        _atomic_text(worker.owner_path, f'{os.getpid()}\n')
        if console_origin:
            _atomic_text(worker.origin_path, f'{_checked_console_origin(console_origin)}\n')
        worker.stop_path.unlink(missing_ok=True)
        self._workers[worker.instance_id] = worker

    def connect(self, instance_id: str, console_origin: str) -> dict[str, Any]:
        with self._lock:
            connection_lock = self._connection_locks.setdefault(instance_id, threading.Lock())
        with connection_lock:
            return self._connect_instance(instance_id, console_origin)

    def _connect_instance(self, instance_id: str, console_origin: str) -> dict[str, Any]:
        origin = _checked_console_origin(console_origin)
        instance = self.hub.registry.get_instance(instance_id, include_profiles=True)
        if not bool(instance.get('enabled', True)):
            raise ScheduleError('Player 实例已停用', error_id='schedule.instance_disabled')
        if str(instance.get('status') or '') != 'ready':
            raise ScheduleError(
                str(instance.get('error_message') or 'Player 实例需要检查'),
                error_id=str(instance.get('error_id') or 'schedule.instance_unavailable'),
                action='verify_installation',
            )
        with self._lock:
            current = self._workers.get(instance_id)
            if current:
                try:
                    state = _request_json(current.origin, '/api/vnext/player/runtime/state', timeout=0.8)
                except ScheduleError:
                    self._workers.pop(instance_id, None)
                else:
                    self._adopt(current, origin)
                    return self._session(instance, current, state)

            recovered = self._worker_from_descriptor(instance)
            if recovered:
                self._adopt(recovered, origin)
                state = _request_json(recovered.origin, '/api/vnext/player/runtime/state')
                return self._session(instance, recovered, state)

            descriptor_path, owner_path, stop_path, origin_path = self._paths(instance)
            descriptor_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor_path.unlink(missing_ok=True)
            stop_path.unlink(missing_ok=True)
            _atomic_text(owner_path, f'{os.getpid()}\n')
            _atomic_text(origin_path, f'{origin}\n')
            process = self.hub.registry.launch_instance_console_worker(
                instance_id,
                descriptor_path=descriptor_path,
                console_origin_path=origin_path,
                console_origin=origin,
                console_parent_pid=os.getpid(),
            )

        deadline = time.monotonic() + self.startup_timeout
        descriptor: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            descriptor = _read_json(descriptor_path)
            if descriptor:
                try:
                    port = int(descriptor.get('port') or 0)
                except (TypeError, ValueError):
                    port = 0
                if (
                    str(descriptor.get('instance_id') or '') == instance_id
                    and int(descriptor.get('process_id') or 0) == int(process.pid)
                    and 1 <= port <= 65535
                ):
                    worker = _Worker(
                        instance_id=instance_id,
                        descriptor_path=descriptor_path,
                        owner_path=owner_path,
                        stop_path=stop_path,
                        origin_path=origin_path,
                        process_id=int(process.pid),
                        origin=f'http://127.0.0.1:{port}',
                        process=process,
                    )
                    try:
                        state = _request_json(worker.origin, '/api/vnext/player/runtime/state', timeout=0.8)
                    except ScheduleError:
                        time.sleep(0.05)
                        continue
                    with self._lock:
                        self._adopt(worker, origin)
                    return self._session(instance, worker, state)
            time.sleep(0.05)

        stop_path.touch(exist_ok=True)
        raise ScheduleError(
            'Player 实例工作进程未能在限定时间内启动',
            error_id='schedule.instance_worker_start_timeout',
            action='restart_instance_worker',
            transient=True,
        )

    def _session(
        self,
        instance: dict[str, Any],
        worker: _Worker,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        execution = state.get('execution') if isinstance(state.get('execution'), dict) else None
        status = self._execution_status(state) or 'ready'
        if status in {'completed', 'cancelled'}:
            status = 'ready'
        elif status == 'failed':
            status = 'failed'
        return {
            'instance_id': worker.instance_id,
            'instance_name': str(instance.get('display_name') or worker.instance_id),
            'product_id': str(instance.get('product_id') or ''),
            'process_id': worker.process_id,
            'port': int(urlparse(worker.origin).port or 0),
            'status': status,
            'frame_url': self._frame_url(worker),
            'execution': execution,
        }

    def state(self, instance_id: str) -> dict[str, Any]:
        instance = self.hub.registry.get_instance(instance_id, include_profiles=False)
        with self._lock:
            worker = self._workers.get(instance_id) or self._worker_from_descriptor(instance)
            if worker:
                self._adopt(worker)
        if not worker:
            return {
                'instance_id': instance_id,
                'instance_name': str(instance.get('display_name') or instance_id),
                'product_id': str(instance.get('product_id') or ''),
                'process_id': 0,
                'port': 0,
                'status': 'stopped',
                'frame_url': '',
                'execution': None,
            }
        try:
            state = _request_json(worker.origin, '/api/vnext/player/runtime/state')
        except ScheduleError:
            return {
                **self._session(instance, worker, {}),
                'status': 'unreachable',
                'error_id': 'schedule.instance_worker_unreachable',
                'error_message': '实例工作进程已失去连接，可以原位重启。',
            }
        return self._session(instance, worker, state)

    def list_instances(self) -> dict[str, Any]:
        instances = self.hub.registry.list_instances(include_profiles=True)
        connected: dict[str, dict[str, Any]] = {}
        for instance in instances:
            instance_id = str(instance['instance_id'])
            try:
                connected[instance_id] = self.state(instance_id)
            except ScheduleError:
                continue
        return {
            'schema_version': 1,
            'installations': self.hub.registry.list_installations(include_profiles=False),
            'instances': [
                {
                    **instance,
                    'console': connected.get(str(instance['instance_id']), {
                        'status': 'stopped', 'process_id': 0, 'port': 0,
                        'frame_url': '', 'execution': None,
                    }),
                }
                for instance in instances
            ],
        }

    @staticmethod
    def _support_execution(state: dict[str, Any] | None) -> dict[str, Any] | None:
        execution = state.get('execution') if isinstance(state, dict) else None
        if not isinstance(execution, dict):
            return None
        return {
            'execution_id': str(execution.get('execution_id') or ''),
            'status': str(execution.get('status') or ''),
            'error_id': str(execution.get('error_id') or ''),
            'error': str(execution.get('error') or ''),
            'started_at': str(execution.get('started_at') or ''),
            'finished_at': str(execution.get('finished_at') or ''),
            'current_instruction_id': str(execution.get('current_instruction_id') or ''),
            'current_source': {
                key: str(value)
                for key, value in (
                    execution.get('current_source')
                    if isinstance(execution.get('current_source'), dict)
                    else {}
                ).items()
                if key in {'function_id', 'statement_id', 'value_id', 'field_path'}
            },
        }

    def create_support_bundle(self, instance_id: str) -> Path:
        """Create an on-demand, bounded bundle even when the worker is dead."""

        instance = self.hub.registry.get_instance(instance_id, include_profiles=False)
        instance_root = Path(str(instance['data_root'])).resolve()
        descriptor_path, owner_path, stop_path, origin_path = self._paths(instance)
        descriptor = _read_json(descriptor_path) or {}
        descriptor = {
            key: descriptor.get(key)
            for key in (
                'schema_version', 'instance_id', 'instance_name', 'process_id',
                'port', 'started_at',
            )
            if descriptor.get(key) is not None
        }

        runtime_state: dict[str, Any] | None = None
        connection_error = ''
        port = 0
        try:
            port = int(descriptor.get('port') or 0)
        except (TypeError, ValueError):
            port = 0
        if str(descriptor.get('instance_id') or '') == instance_id and 1 <= port <= 65535:
            try:
                runtime_state = _request_json(
                    f'http://127.0.0.1:{port}',
                    '/api/vnext/player/runtime/state',
                    timeout=0.8,
                )
            except ScheduleError as exc:
                connection_error = f'{exc.error_id}: {exc}'
        elif descriptor:
            connection_error = 'schedule.instance_worker_descriptor_invalid: 工作进程描述与实例不一致'
        else:
            connection_error = 'schedule.instance_worker_stopped: 未发现活动工作进程描述'

        installation = instance.get('installation') if isinstance(instance.get('installation'), dict) else {}
        execution = self._support_execution(runtime_state)
        try:
            process_id = int(descriptor.get('process_id') or 0)
        except (TypeError, ValueError):
            process_id = 0
        with self._lock:
            current = self._workers.get(instance_id)
        exit_code = current.process.poll() if current and current.process is not None else None
        summary = {
            'schema_version': 1,
            'created_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
            'product': {
                'product_id': str(instance.get('product_id') or ''),
                'display_name': str(installation.get('display_name') or ''),
                'release_id': str(installation.get('release_id') or ''),
            },
            'instance': {
                'instance_id': str(instance.get('instance_id') or ''),
                'display_name': str(instance.get('display_name') or ''),
                'revision': int(instance.get('revision') or 0),
                'registry_status': str(instance.get('status') or ''),
            },
            'worker': {
                'reachable': runtime_state is not None,
                'process_id': process_id,
                'port': port,
                'exit_code': exit_code,
                'connection_error': connection_error,
                'owner_lease_present': owner_path.is_file(),
                'stop_requested': stop_path.is_file(),
                'origin_descriptor_present': origin_path.is_file(),
            },
            'execution': execution,
            'host': {
                'platform': platform.platform(),
                'python': platform.python_version(),
                'frozen': bool(getattr(sys, 'frozen', False)),
            },
        }
        privacy = {
            'schema_version': 1,
            'generated_only_after_user_action': True,
            'automatically_uploaded': False,
            'includes_full_recording': False,
            'excluded': ['Player 方案值', '项目源码', '完整录制', '任意用户目录'],
            'note': '若存在最近一次运行失败诊断，其中可能包含按既有脱敏规则处理的变量与一张失败截图。',
        }

        export_root = instance_root / 'support' / 'exports'
        export_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = export_root / f'easycode-support-{stamp}-{uuid.uuid4().hex[:8]}.zip'
        temporary = target.with_suffix('.tmp')
        included: list[dict[str, Any]] = []
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                def add_text(name: str, value: str) -> None:
                    payload = value.encode('utf-8')
                    archive.writestr(name, payload)
                    included.append({'name': name, 'size': len(payload)})

                add_text('summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
                add_text('privacy.json', json.dumps(privacy, ensure_ascii=False, indent=2))
                if descriptor:
                    add_text('worker-descriptor.json', json.dumps(descriptor, ensure_ascii=False, indent=2))

                log_sources = (
                    ('instance-player.log', instance_root / 'logs' / 'player.log', 2 * 1024 * 1024),
                    ('instance-player.log.1', instance_root / 'logs' / 'player.log.1', 1024 * 1024),
                    ('instance-startup.log', instance_root / 'logs' / 'startup.log', 512 * 1024),
                    ('instance-native-crash.log', instance_root / 'logs' / 'native-crash.log', 512 * 1024),
                    ('console-player.log', _default_controller_logs() / 'player.log', 1024 * 1024),
                )
                for name, source, limit in log_sources:
                    content = _tail_text(source, limit=limit)
                    if content:
                        add_text(f'logs/{name}', content)

                diagnostic_root = instance_root / 'runtime' / 'diagnostics'
                candidates = sorted(
                    diagnostic_root.glob('*/diagnostic.zip') if diagnostic_root.is_dir() else (),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    latest = candidates[0]
                    try:
                        if latest.stat().st_size <= 24 * 1024 * 1024:
                            archive.write(latest, 'latest-run-diagnostic.zip')
                            included.append({'name': 'latest-run-diagnostic.zip', 'size': latest.stat().st_size})
                    except OSError:
                        pass
                add_text('manifest.json', json.dumps({
                    'schema_version': 1,
                    'entries': included,
                }, ensure_ascii=False, indent=2))
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

        # The downloaded copy belongs to the user. Server-side staging remains
        # bounded and recoverable without a background cleanup task.
        exports = sorted(export_root.glob('easycode-support-*.zip'), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in exports[3:]:
            try:
                stale.unlink()
            except OSError:
                continue
        return target

    def close_status(self) -> dict[str, Any]:
        snapshot = self.list_instances()
        active_instances = []
        for instance in snapshot['instances']:
            session = instance.get('console') if isinstance(instance.get('console'), dict) else {}
            status = self._execution_status(session)
            if status not in _ACTIVE_RUN_STATES:
                continue
            active_instances.append({
                'instance_id': str(instance.get('instance_id') or ''),
                'instance_name': str(instance.get('display_name') or instance.get('instance_id') or ''),
                'status': status,
            })
        return {
            'schema_version': 1,
            'active_count': len(active_instances),
            'active_instances': active_instances,
        }

    def prepare_close(self, *, stop_active: bool = False) -> dict[str, Any]:
        status = self.close_status()
        active_instances = list(status['active_instances'])
        if active_instances and not stop_active:
            return {
                **status,
                'ready': False,
                'requires_confirmation': True,
                'stopped_instance_count': 0,
            }

        stop_request_failures: list[dict[str, Any]] = []
        if stop_active:
            for instance in active_instances:
                try:
                    self.control(str(instance['instance_id']), 'stop')
                except ScheduleError as exc:
                    # The orderly worker shutdown below remains authoritative
                    # and will cancel Runtime during ASGI lifespan.  Preserve
                    # this detail so a forced path is visible in diagnostics.
                    stop_request_failures.append({
                        'instance_id': str(instance['instance_id']),
                        'instance_name': str(instance['instance_name']),
                        'error_id': exc.error_id,
                        'message': str(exc),
                    })

        with self._lock:
            worker_ids = list(self._workers)
        cleanup_failures: list[dict[str, Any]] = []
        for instance_id in worker_ids:
            try:
                self.stop_worker(instance_id, allow_active=True)
            except ScheduleError as exc:
                cleanup_failures.append({
                    'instance_id': instance_id,
                    'error_id': exc.error_id,
                    'message': str(exc),
                })
        if cleanup_failures:
            raise ScheduleError(
                '仍有 Player 实例未能安全停止，请保留窗口并重试',
                error_id='schedule.console_close_stop_failed',
                transient=True,
                action='retry_close',
                diagnostics=cleanup_failures,
            )
        return {
            'schema_version': 1,
            'ready': True,
            'requires_confirmation': False,
            'active_count': len(active_instances),
            'active_instances': active_instances,
            'stopped_instance_count': len(worker_ids),
            'forced_stop_requests': stop_request_failures,
        }

    def control(self, instance_id: str, action: str) -> dict[str, Any]:
        state = self.state(instance_id)
        execution = state.get('execution') if isinstance(state.get('execution'), dict) else None
        execution_id = str((execution or {}).get('execution_id') or '')
        status = str((execution or {}).get('status') or '')
        if not execution_id or status not in _ACTIVE_RUN_STATES:
            raise ScheduleError(
                '该实例当前没有可控制的运行',
                error_id='schedule.instance_run_not_active',
            )
        origin = f"http://127.0.0.1:{int(state['port'])}"
        if action == 'pause':
            if status not in {'queued', 'running'}:
                raise ScheduleError('该实例当前不能暂停', error_id='schedule.instance_run_not_running')
            result = _request_json(origin, f'/api/vnext/runs/{execution_id}/pause', method='POST')
        elif action == 'resume':
            if status != 'paused':
                raise ScheduleError('该实例当前未暂停', error_id='schedule.instance_run_not_paused')
            result = _request_json(origin, f'/api/vnext/runs/{execution_id}/resume', method='POST')
        elif action == 'stop':
            result = _request_json(origin, f'/api/vnext/runs/{execution_id}', method='DELETE')
        else:
            raise ScheduleError('未知的实例运行控制', error_id='schedule.instance_control_invalid')
        return {'ok': True, 'instance_id': instance_id, 'action': action, 'execution': result}

    def stop_worker(self, instance_id: str, *, allow_active: bool = False) -> dict[str, Any]:
        state = self.state(instance_id)
        worker = self._workers.get(instance_id)
        if not worker:
            return {'ok': True, 'instance_id': instance_id, 'status': 'stopped'}
        if self._execution_status(state) in _ACTIVE_RUN_STATES and not allow_active:
            raise ScheduleError(
                '实例正在运行；请先停止任务再重启工作进程',
                error_id='schedule.instance_worker_active',
                action='stop_instance_run',
            )
        worker.owner_path.unlink(missing_ok=True)
        worker.stop_path.touch(exist_ok=True)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if worker.process is not None and worker.process.poll() is not None:
                break
            try:
                _request_json(worker.origin, '/api/vnext/player/runtime/state', timeout=0.25)
            except ScheduleError:
                break
            time.sleep(0.05)
        if worker.process is not None and worker.process.poll() is None:
            outcome = terminate_process_tree(worker.process)
            if not bool(outcome.get('terminated')) and outcome.get('reason') != 'already_exited':
                raise ScheduleError(
                    'Player 实例工作进程未能退出',
                    error_id='schedule.instance_worker_stop_failed',
                    action='retry_close',
                    transient=True,
                    diagnostics=[outcome],
                )
        elif worker.process is None:
            try:
                _request_json(worker.origin, '/api/vnext/player/runtime/state', timeout=0.25)
            except ScheduleError:
                time.sleep(0.2)
            if not _terminate_adopted_worker(worker.process_id):
                raise ScheduleError(
                    '接管的 Player 实例工作进程未能退出',
                    error_id='schedule.instance_worker_stop_failed',
                    action='retry_close',
                    transient=True,
                    diagnostics=[{'instance_id': instance_id, 'process_id': worker.process_id}],
                )
        with self._lock:
            self._workers.pop(instance_id, None)
        return {'ok': True, 'instance_id': instance_id, 'status': 'stopped'}

    def restart(self, instance_id: str, console_origin: str) -> dict[str, Any]:
        self.stop_worker(instance_id)
        return self.connect(instance_id, console_origin)

    def delete_instance(self, instance_id: str, *, expected_revision: int) -> dict[str, Any]:
        state = self.state(instance_id)
        if self._execution_status(state) in _ACTIVE_RUN_STATES:
            raise ScheduleError(
                '实例正在运行；请先停止当前任务再删除实例',
                error_id='schedule.instance_worker_active',
                action='stop_instance_run',
            )
        for plan in self.hub.schedule.list_plans():
            entries = plan.get('entries') if isinstance(plan.get('entries'), list) else []
            if any(str(item.get('instance_id') or '') == instance_id for item in entries if isinstance(item, dict)):
                raise ScheduleError(
                    f"实例仍被运行计划“{plan.get('name') or plan.get('schedule_id')}”引用，请先移除该条目",
                    error_id='schedule.instance_reference_conflict',
                    action='open_schedules',
                )
        self.stop_worker(instance_id)
        return self.hub.registry.delete_instance(
            instance_id,
            expected_revision=expected_revision,
        )

    def shutdown(self) -> None:
        with self._lock:
            instance_ids = list(self._workers)
        for instance_id in instance_ids:
            try:
                state = self.state(instance_id)
                active = self._execution_status(state) in _ACTIVE_RUN_STATES
                worker = self._workers.get(instance_id)
                if worker and active:
                    # Do not destroy an explicit running/paused task merely
                    # because its visible console closed.  The worker exits
                    # after the task ends unless a new console adopts it.
                    worker.owner_path.unlink(missing_ok=True)
                    continue
                self.stop_worker(instance_id)
            except Exception:
                continue
        with self._lock:
            self._workers.clear()


_default_console: PlayerConsoleV1 | None = None
_default_lock = threading.Lock()


def get_player_console_v1() -> PlayerConsoleV1:
    global _default_console
    with _default_lock:
        if _default_console is None:
            _default_console = PlayerConsoleV1()
        return _default_console


def shutdown_player_console_v1() -> None:
    global _default_console
    with _default_lock:
        current, _default_console = _default_console, None
    if current is not None:
        current.shutdown()


__all__ = ['PlayerConsoleV1', 'get_player_console_v1', 'shutdown_player_console_v1']
