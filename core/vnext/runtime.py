"""Cancellable in-process ECIR sessions for the vNext runtime boundary."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import os
import random
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, TextIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .json_schema_v6 import (
    JsonSchemaDefinitionError,
    JsonSchemaValueError,
    validate_json_schema,
)
from .project_variables_v6 import (
    runtime_project_value_conforms,
    validate_runtime_constraints,
)


# Keep the dispatcher boundary explicit without importing PlatformRuntimeV6 at
# module load time (that adapter imports RuntimeFailure from this module).
_PLATFORM_RUNTIME_OPCODES = frozenset({
    'target.wait_online', 'target.status',
    'host.app.start', 'host.app.wait_exit',
    'host.app.is_running', 'host.app.stop',
    'clipboard.read_text', 'clipboard.write_text',
})


@dataclass
class RuntimeEvent:
    sequence: int
    timestamp: str
    level: str
    category: str
    message: str
    instruction_id: str = ''


@dataclass
class _ListenerRegistration:
    listener_id: str
    instruction_id: str
    name: str
    sender: Any
    receive_slot: str
    condition: Any
    handler_function_id: str
    handler_arguments: dict[str, Any]
    scope_slots: dict[str, Any] = field(repr=False)


@dataclass
class RuntimeSession:
    execution_id: str
    status: str = 'queued'
    started_at: str = ''
    finished_at: str = ''
    error: str = ''
    error_id: str = ''
    error_details: Any = None
    events: deque[RuntimeEvent] = field(default_factory=deque)
    next_event_sequence: int = 0
    cancel_requested: bool = False
    pause_requested: bool = False
    pause_after_instruction: bool = False
    current_instruction_id: str = ''
    current_source: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    project_variables: dict[str, Any] = field(default_factory=dict)
    project_variable_definitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    local_variable_definitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    breakpoints: set[str] = field(default_factory=set)
    project_path: str = ''
    runtime_data_directory: str = ''
    dangerous_confirmations: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostic_bundle: str = ''
    failure_frame: str = ''
    event_log_path: str = ''
    finished_monotonic: float = 0.0
    last_access_monotonic: float = field(default_factory=time.monotonic)
    worker_pid: int = 0
    worker_started: bool = False
    hard_timeout_seconds: float = 0.0
    cancel_deadline: float = 0.0
    target_key: str = ''
    message_context: dict[str, Any] = field(default_factory=dict)
    current_listener_id: str = ''
    current_message_id: str = ''
    _worker_proxy: Any = field(default=None, repr=False)
    _message_runtime: Any = field(default=None, repr=False)
    _network_runtime: Any = field(default=None, repr=False)
    _platform_runtime: Any = field(default=None, repr=False)
    _log_stream: TextIO | None = field(default=None, repr=False)
    _resume_gate: threading.Event | None = field(default_factory=threading.Event, repr=False)
    _listeners: dict[str, _ListenerRegistration] = field(default_factory=dict, repr=False)
    _dispatching_listener: bool = field(default=False, repr=False)
    _failed_listener_id: str = field(default='', repr=False)
    _failed_message_id: str = field(default='', repr=False)
    _call_stack: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _failure_call_stack: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def snapshot(self, after_sequence: int | None = None) -> dict[str, Any]:
        retained = list(self.events)
        oldest = retained[0].sequence if retained else self.next_event_sequence + 1
        cursor = max(0, int(after_sequence or 0))
        selected = retained if after_sequence is None else [item for item in retained if item.sequence > cursor]
        listener_id = self.current_listener_id or (
            self._failed_listener_id if self.status == 'failed' else ''
        )
        message_id = self.current_message_id or (
            self._failed_message_id if self.status == 'failed' else ''
        )
        current_function_id = str(self.current_source.get('function_id') or '')
        value_entries = {
            'local': [
                {
                    'id': symbol_id,
                    'display_name': str(definition.get('display_name') or symbol_id),
                    'value_type': str(definition.get('value_type') or 'any'),
                    'kind': str(definition.get('kind') or 'local'),
                    'value': copy.deepcopy(value),
                }
                for symbol_id, value in self.variables.items()
                for definition in [self.local_variable_definitions.get(symbol_id) or {}]
                if not current_function_id
                or not definition
                or str(definition.get('function_id') or '') == current_function_id
            ],
            'project': [
                {
                    'id': variable_id,
                    'display_name': str(definition.get('display_name') or variable_id),
                    'value_type': str(definition.get('value_type') or 'any'),
                    'kind': 'project',
                    'value': copy.deepcopy(value),
                }
                for variable_id, value in self.project_variables.items()
                for definition in [self.project_variable_definitions.get(variable_id) or {}]
            ],
        }
        return {
            'execution_id': self.execution_id, 'status': self.status,
            'started_at': self.started_at, 'finished_at': self.finished_at,
            'error': self.error, 'error_id': self.error_id,
            'error_details': copy.deepcopy(self.error_details),
            'events': [asdict(item) for item in selected],
            'event_cursor': self.next_event_sequence,
            'oldest_event_sequence': oldest if retained else 0,
            'events_truncated': bool(after_sequence is not None and cursor > 0 and retained and oldest > cursor + 1),
            'event_log_available': bool(self.event_log_path),
            'worker': {
                'pid': self.worker_pid,
                'started': self.worker_started,
                'isolated': bool(self._worker_proxy),
            },
            'current_instruction_id': self.current_instruction_id,
            'current_source': dict(self.current_source), 'variables': dict(self.variables),
            'current_listener_id': listener_id,
            'current_message_id': message_id,
            'call_stack': copy.deepcopy(
                self._failure_call_stack
                if self.status == 'failed' and self._failure_call_stack
                else self._call_stack
            ),
            'project_variables': copy.deepcopy(self.project_variables),
            'value_entries': value_entries,
            'breakpoints': sorted(self.breakpoints),
            'diagnostic_available': bool(self.diagnostic_bundle),
            'failure_frame_available': bool(self.failure_frame),
        }


class RuntimeFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_id: str = 'runtime.failure',
        transient: bool = False,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.error_id = error_id
        self.transient = transient
        self.details = details


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _TargetScopeManager:
    """Own the serial logical-target stack for one in-process execution."""

    def __init__(
        self,
        runtime: VNextRuntime,
        session: RuntimeSession,
        ecir: dict[str, Any],
        initial_driver: Any,
        factory: Callable[[str, dict[str, Any]], Any] | None,
    ) -> None:
        self._runtime = runtime
        self._session = session
        self._project_path = str(ecir.get('project_path') or session.project_path or '')
        self._factory = factory
        self._targets = {
            str(item.get('target_id') or ''): dict(item)
            for item in (ecir.get('targets') or [])
            if isinstance(item, dict) and str(item.get('target_id') or '')
        }
        self._stack: list[Any] = [initial_driver]
        self._closed = False

    @property
    def current(self) -> Any:
        return self._stack[-1]

    @property
    def target(self) -> dict[str, Any]:
        return dict(getattr(self.current, 'target', {}) or {}) if self.current is not None else {}

    def resolve_target_definition(self, target_id: str) -> dict[str, Any] | None:
        """Resolve only targets locked into this execution's ECIR closure."""

        target = self._targets.get(str(target_id or ''))
        return dict(target) if target is not None else None

    def __getattr__(self, name: str) -> Any:
        current = self.current
        if current is None:
            raise AttributeError(name)
        return getattr(current, name)

    def _create(self, target: dict[str, Any]) -> Any:
        if target.get('type') == 'android_local':
            raise RuntimeFailure(
                'Windows Runtime 不能进入 Android 本机目标作用域',
                error_id='target.host_unsupported',
            )
        if self._factory is not None:
            return self._factory(self._project_path, target)
        from .target_runtime import create_target_driver

        return create_target_driver(self._project_path, target)

    @contextlib.contextmanager
    def enter(self, target_id: str, instruction_id: str):
        if self._session.cancel_requested:
            raise RuntimeFailure('目标切换已取消', error_id='runtime.cancelled')
        target = self._targets.get(target_id)
        if target is None:
            raise RuntimeFailure(
                f'目标引用已失效：{target_id}', error_id='target.reference_missing',
            )
        current = self.current
        current_id = str(getattr(current, 'target', {}).get('target_id') or '') if current else ''
        if current_id == target_id:
            self._runtime._event(
                self._session, 'info', 'target', f'继续使用当前目标：{target_id}', instruction_id,
            )
            yield current
            return

        reusable = next((
            driver for driver in reversed(self._stack)
            if str(getattr(driver, 'target', {}).get('target_id') or '') == target_id
        ), None)
        key = self._runtime._target_key(target)
        acquired = False
        created = False
        driver = reusable
        try:
            if reusable is None:
                self._runtime._acquire_target(self._session, key)
                acquired = True
                driver = self._create(target)
                created = True
                if driver is None:
                    raise RuntimeFailure(
                        f'目标没有可用驱动：{target_id}', error_id='target.driver_unavailable',
                    )
            # A logical switch is committed only after the target proves it can
            # provide a current frame. This also refreshes a driver reused from
            # an outer scope; the previous target remains active on failure.
            driver.capture_frame()
            self._stack.append(driver)
            self._runtime._event(
                self._session, 'info', 'target',
                f'已切换目标：{current_id or "无目标"} -> {target_id}', instruction_id,
            )
            yield driver
        except Exception as exc:
            self._runtime._event(
                self._session, 'error', 'target',
                f'目标切换失败：{current_id or "无目标"} -> {target_id}；{exc}',
                instruction_id,
            )
            raise
        finally:
            if len(self._stack) > 1 and self._stack[-1] is driver:
                self._stack.pop()
                restored = str(
                    getattr(self.current, 'target', {}).get('target_id') or ''
                ) if self.current is not None else ''
                self._runtime._event(
                    self._session, 'info', 'target',
                    f'已恢复逻辑目标：{restored or "无目标"}', instruction_id,
                )
            if created and driver is not None and hasattr(driver, 'close'):
                with contextlib.suppress(Exception):
                    driver.close()
            if acquired:
                self._runtime._release_target(self._session, key)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        initial = self._stack[0] if self._stack else None
        self._stack.clear()
        if initial is not None and hasattr(initial, 'close'):
            with contextlib.suppress(Exception):
                initial.close()


def _runtime_value_conforms(value: Any, type_id: str) -> bool:
    """Validate the single format-6 ASCII type contract."""

    return runtime_project_value_conforms(value, str(type_id))


def _resolve_wait_target(value: Any, past_policy: str) -> datetime:
    """Resolve a user-facing local wall-clock value without hiding day rollover."""

    if isinstance(value, dict) and value.get('kind') == 'time':
        value = value.get('value')
    if not isinstance(value, str) or not value.strip():
        raise RuntimeFailure(
            '等待.直到 的时间必须是 HH:MM、HH:MM:SS 或 ISO 日期时间',
            error_id='wait.time_invalid',
        )
    raw = value.strip()
    now = datetime.now().astimezone()
    time_only = False
    parsed: datetime | None = None
    for pattern in ('%H:%M:%S', '%H:%M'):
        try:
            clock = datetime.strptime(raw, pattern).time()
            parsed = now.replace(hour=clock.hour, minute=clock.minute, second=clock.second, microsecond=0)
            time_only = True
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError as exc:
            raise RuntimeFailure(
                f'无法识别等待时间：{raw}', error_id='wait.time_invalid'
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        else:
            parsed = parsed.astimezone(now.tzinfo)
    if time_only and parsed <= now:
        policy = str(past_policy or 'next_day').strip()
        if policy in {'next_day', '次日'}:
            parsed += timedelta(days=1)
        elif policy in {'immediate', '立即'}:
            return now
        elif policy in {'error', '报错'}:
            raise RuntimeFailure(
                f'当日时刻 {raw} 已过', error_id='wait.time_already_passed'
            )
        else:
            raise RuntimeFailure(
                '等待.直到 的当日已过策略无效', error_id='wait.time_invalid'
            )
    return parsed


class VNextRuntime:
    def __init__(
        self,
        *,
        event_buffer_size: int = 1000,
        max_sessions: int = 100,
        session_ttl_seconds: float = 24 * 60 * 60,
        use_worker_process: bool = False,
        persist_event_log: bool = True,
        event_sink: Callable[[RuntimeEvent], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._events_changed = threading.Condition(self._lock)
        self._sessions: dict[str, RuntimeSession] = {}
        self._event_buffer_size = max(10, int(event_buffer_size))
        self._max_sessions = max(1, int(max_sessions))
        self._session_ttl_seconds = max(1.0, float(session_ttl_seconds))
        self._use_worker_process = bool(use_worker_process)
        self._persist_event_log = bool(persist_event_log)
        self._event_sink = event_sink
        self._target_owners: dict[str, str] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

    def _event(self, session: RuntimeSession, level: str, category: str, message: str, instruction_id: str = '') -> None:
        with self._lock:
            session.next_event_sequence += 1
            event = RuntimeEvent(session.next_event_sequence, self._now(), level, category, message, instruction_id)
            session.events.append(event)
            if session._log_stream is not None:
                try:
                    session._log_stream.write(json.dumps(asdict(event), ensure_ascii=False) + '\n')
                except (OSError, ValueError):
                    with contextlib.suppress(Exception):
                        session._log_stream.close()
                    session._log_stream = None
            self._events_changed.notify_all()
        if self._event_sink is not None:
            self._event_sink(event)

    def _worker_event(self, session: RuntimeSession, raw: dict[str, Any]) -> None:
        sequence = int(raw.get('sequence') or 0)
        with self._lock:
            if sequence <= session.next_event_sequence:
                return
            event = RuntimeEvent(
                sequence=sequence,
                timestamp=str(raw.get('timestamp') or self._now()),
                level=str(raw.get('level') or 'info'),
                category=str(raw.get('category') or 'runtime'),
                message=str(raw.get('message') or ''),
                instruction_id=str(raw.get('instruction_id') or ''),
            )
            session.next_event_sequence = sequence
            session.events.append(event)
            self._events_changed.notify_all()

    def _prepare_event_log(self, session: RuntimeSession) -> None:
        instance_root = str(os.environ.get('EASYCODE_PLAYER_DATA_DIR') or '').strip()
        if instance_root:
            directory = os.path.join(os.path.realpath(os.path.expanduser(instance_root)), 'runtime', 'events')
        elif session.project_path and os.path.isdir(session.project_path) and os.access(session.project_path, os.W_OK):
            directory = os.path.join(session.project_path, '.easycode', 'runtime-logs')
        else:
            directory = os.path.join(tempfile.gettempdir(), 'EasyCode', 'runtime-logs')
        if not self._persist_event_log:
            return
        try:
            os.makedirs(directory, exist_ok=True)
            session.event_log_path = os.path.join(directory, f'{session.execution_id}.jsonl')
            # This stream intentionally remains open for the runtime session and
            # is closed centrally by _close_event_log when the session finishes.
            session._log_stream = open(  # noqa: SIM115
                session.event_log_path,
                'a',
                encoding='utf-8',
                buffering=1,
            )
        except OSError:
            session.event_log_path = ''
            session._log_stream = None

    @staticmethod
    def _close_event_log(session: RuntimeSession) -> None:
        if session._log_stream is not None:
            with contextlib.suppress(Exception):
                session._log_stream.close()
            session._log_stream = None

    @staticmethod
    def _safe_remove_session_artifacts(session: RuntimeSession) -> None:
        instance_root = str(os.environ.get('EASYCODE_PLAYER_DATA_DIR') or '').strip()
        persistent_diagnostics = (
            os.path.realpath(os.path.join(os.path.expanduser(instance_root), 'runtime', 'diagnostics'))
            if instance_root
            else ''
        )

        def is_persistent(path: str) -> bool:
            if not persistent_diagnostics:
                return False
            try:
                return os.path.commonpath((persistent_diagnostics, path)) == persistent_diagnostics
            except ValueError:
                return False

        candidates = {session.event_log_path, session.diagnostic_bundle, session.failure_frame}
        for raw in candidates:
            if not raw:
                continue
            path = os.path.realpath(raw)
            if is_persistent(path):
                continue
            if os.path.basename(path).startswith(session.execution_id) or session.execution_id in path.split(os.sep):
                with contextlib.suppress(OSError):
                    if os.path.isfile(path):
                        os.remove(path)
        bundle = os.path.realpath(session.diagnostic_bundle) if session.diagnostic_bundle else ''
        directory = os.path.dirname(bundle) if bundle else ''
        if (
            directory
            and not is_persistent(directory)
            and os.path.basename(directory) == session.execution_id
            and os.path.basename(os.path.dirname(directory)) == 'diagnostics'
        ):
            with contextlib.suppress(OSError):
                shutil.rmtree(directory)

    @staticmethod
    def _prune_persistent_diagnostics(root: str, *, keep: int = 5, byte_limit: int = 64 * 1024 * 1024) -> None:
        try:
            directories = sorted(
                (
                    path for path in (os.path.join(root, name) for name in os.listdir(root))
                    if os.path.isdir(path)
                ),
                key=os.path.getmtime,
                reverse=True,
            )
        except OSError:
            return
        retained_bytes = 0
        for index, directory in enumerate(directories):
            size = 0
            for parent, _folders, files in os.walk(directory):
                for name in files:
                    with contextlib.suppress(OSError):
                        size += os.path.getsize(os.path.join(parent, name))
            if index < max(1, keep) and retained_bytes + size <= max(1024 * 1024, byte_limit):
                retained_bytes += size
                continue
            with contextlib.suppress(OSError):
                shutil.rmtree(directory)

    def _prune_sessions(self, *, reserve_slots: int = 0) -> None:
        now = time.monotonic()
        terminal = [
            session for session in self._sessions.values()
            if session.status in {'completed', 'failed', 'cancelled'} and session.finished_monotonic
        ]
        expired = {session.execution_id for session in terminal if now - session.finished_monotonic >= self._session_ttl_seconds}
        survivors = sorted(
            (session for session in terminal if session.execution_id not in expired),
            key=lambda item: item.finished_monotonic,
        )
        overflow = max(0, len(self._sessions) - len(expired) + max(0, reserve_slots) - self._max_sessions)
        expired.update(session.execution_id for session in survivors[:overflow])
        for execution_id in expired:
            session = self._sessions.pop(execution_id, None)
            if session is not None:
                self._close_event_log(session)
                self._safe_remove_session_artifacts(session)

    @classmethod
    def _safe_diagnostic_value(cls, value: Any, key: str = '') -> Any:
        if any(marker in key.lower() for marker in ('password', 'token', 'secret', '密码', '令牌', '密钥')):
            return '<已隐藏>'
        if isinstance(value, dict):
            is_received_message = value.get('record_type') == 'received_message'
            return {
                str(name): (
                    '<消息正文已隐藏>'
                    if is_received_message and str(name) == 'content'
                    else cls._safe_diagnostic_value(child, str(name))
                )
                for name, child in value.items()
            }
        if isinstance(value, list):
            return [cls._safe_diagnostic_value(item) for item in value[:200]]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return repr(value)[:500]

    def _create_diagnostics(self, session: RuntimeSession, driver: Any) -> None:
        instance_root = str(os.environ.get('EASYCODE_PLAYER_DATA_DIR') or '').strip()
        root = session.project_path
        persistent_root = ''
        if instance_root:
            persistent_root = os.path.join(
                os.path.realpath(os.path.expanduser(instance_root)), 'runtime', 'diagnostics',
            )
            directory = os.path.join(persistent_root, session.execution_id)
        elif root and os.path.isdir(root) and os.access(root, os.W_OK):
            directory = os.path.join(root, '.easycode', 'diagnostics', session.execution_id)
        else:
            directory = os.path.join(tempfile.gettempdir(), 'EasyCode', 'diagnostics', session.execution_id)
        try:
            os.makedirs(directory, exist_ok=True)
            if driver is not None and hasattr(driver, 'capture_frame'):
                try:
                    frame = driver.capture_frame()
                    frame_path = os.path.join(directory, 'failure-frame.png')
                    if hasattr(frame, 'save'):
                        frame.save(frame_path, format='PNG')
                    elif hasattr(frame, 'shape'):
                        import cv2
                        cv2.imwrite(frame_path, frame)
                    if os.path.isfile(frame_path):
                        session.failure_frame = frame_path
                except Exception as exc:
                    self._event(session, 'warning', 'diagnostic', f'失败帧捕获失败：{exc}')
            report = {
                'schema_version': 1, 'execution_id': session.execution_id,
                'status': session.status, 'error': session.error,
                'error_id': session.error_id,
                'error_details': self._safe_diagnostic_value(session.error_details),
                'started_at': session.started_at, 'finished_at': self._now(),
                'current_instruction_id': session.current_instruction_id,
                'current_source': session.current_source,
                'listener_id': (
                    session.current_listener_id or session._failed_listener_id
                ),
                'message_id': (
                    session.current_message_id or session._failed_message_id
                ),
                'call_stack': copy.deepcopy(
                    session._failure_call_stack or session._call_stack
                ),
                'variables': self._safe_diagnostic_value(session.variables),
                'target': self._safe_diagnostic_value(getattr(driver, 'target', {}) if driver is not None else {}),
                'events': [asdict(item) for item in session.events],
                'event_log_path': session.event_log_path,
            }
            report_path = os.path.join(directory, 'report.json')
            with open(report_path, 'w', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
            bundle = os.path.join(directory, 'diagnostic.zip')
            with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(report_path, 'report.json')
                if session.failure_frame:
                    archive.write(session.failure_frame, 'failure-frame.png')
                if session.event_log_path and os.path.isfile(session.event_log_path):
                    archive.write(session.event_log_path, 'runtime-log.jsonl')
            session.diagnostic_bundle = bundle
            self._event(session, 'info', 'diagnostic', '已生成诊断包')
            if persistent_root:
                self._prune_persistent_diagnostics(persistent_root)
        except Exception as exc:
            self._event(session, 'warning', 'diagnostic', f'诊断包生成失败：{exc}')

    @classmethod
    def _value(cls, value: Any, slots: dict[str, Any]) -> Any:
        if isinstance(value, dict) and value.get('kind') == 'duration':
            return value.get('milliseconds')
        if isinstance(value, dict) and value.get('kind') == 'reference':
            scope = str(value.get('scope') or 'local')
            name = str(value.get('symbol_id') or value.get('variable_id') or value.get('name') or '')
            namespace = slots.get('__project__', {}) if scope == 'project' else slots
            if name not in namespace:
                raise RuntimeFailure(f'变量尚未赋值：{name}', error_id='runtime.variable_unset')
            return namespace[name]
        if isinstance(value, dict) and value.get('kind') == 'member_access':
            owner = cls._value(value.get('source'), slots)
            field_id = str(value.get('field_id') or '')
            if owner is None:
                raise RuntimeFailure(
                    '当前语句需要使用的结果为空，无法继续；如果无结果是正常情况，请先判断“有结果”。',
                    error_id='runtime.optional_empty',
                )
            if isinstance(owner, dict):
                if field_id not in owner:
                    raise RuntimeFailure(f'记录不包含字段：{field_id}', error_id='runtime.member_missing')
                return owner[field_id]
            if not hasattr(owner, field_id):
                raise RuntimeFailure(f'对象不包含字段：{field_id}', error_id='runtime.member_missing')
            return getattr(owner, field_id)
        if isinstance(value, dict) and value.get('kind') == 'list':
            return [cls._value(item, slots) for item in value.get('items') or []]
        if isinstance(value, dict) and value.get('kind') == 'map':
            result: dict[Any, Any] = {}
            for entry in value.get('entries') or []:
                key = cls._value(entry.get('key'), slots)
                if key in result:
                    raise RuntimeFailure('字典中存在重复键', error_id='runtime.map_duplicate_key')
                result[key] = cls._value(entry.get('value'), slots)
            return result
        if isinstance(value, dict) and value.get('kind') == 'record':
            return {key: cls._value(child, slots) for key, child in (value.get('fields') or {}).items()}
        if isinstance(value, dict) and value.get('kind') == 'json':
            return value.get('value')
        if isinstance(value, dict) and value.get('kind') == 'compare':
            left = cls._value(value.get('left'), slots)
            right = cls._value(value.get('right'), slots)
            operation = str(value.get('operator') or '')
            operand_type = str(value.get('operand_type') or '')
            if operand_type == 'datetime':
                try:
                    left = datetime.fromisoformat(str(left).replace('Z', '+00:00'))
                    right = datetime.fromisoformat(str(right).replace('Z', '+00:00'))
                except ValueError as exc:
                    raise RuntimeFailure('日期与时间值无效', error_id='time.value_invalid') from exc
                if (left.tzinfo is None) != (right.tzinfo is None):
                    raise RuntimeFailure('两个日期与时间必须同时包含或同时不包含时区', error_id='time.timezone_mismatch')
            operators = {
                'eq': lambda: left == right, 'ne': lambda: left != right,
                'lt': lambda: left < right, 'lte': lambda: left <= right,
                'gt': lambda: left > right, 'gte': lambda: left >= right,
            }
            if operation not in operators:
                raise RuntimeFailure(f'不支持的比较操作：{operation}', error_id='runtime.operation_unsupported')
            return operators[operation]()
        if isinstance(value, dict) and value.get('kind') == 'condition_group':
            conditions = value.get('conditions') or []
            if value.get('operator') == 'all':
                return all(bool(cls._value(item, slots)) for item in conditions)
            if value.get('operator') == 'any':
                return any(bool(cls._value(item, slots)) for item in conditions)
            raise RuntimeFailure('条件组只支持 all/any', error_id='runtime.operation_unsupported')
        if isinstance(value, dict) and value.get('kind') == 'not':
            return not bool(cls._value(value.get('condition'), slots))
        if isinstance(value, dict) and value.get('kind') == 'operation':
            return cls._pure_operation(value, slots)
        if isinstance(value, dict) and value.get('kind') == 'selector':
            raise RuntimeFailure(
                '逐项选择器只能由集合纯值操作执行',
                error_id='runtime.selector_scope',
            )
        if isinstance(value, dict) and value.get('kind') in {'date', 'datetime', 'time'}:
            return str(value.get('value') or '')
        if isinstance(value, dict) and value.get('kind') in {
            'asset_ref', 'target_ref', 'entity_ref', 'point', 'rect', 'path',
        }:
            return {key: cls._value(child, slots) for key, child in value.items() if key != 'kind'} | {
                'kind': value.get('kind'),
            }
        if isinstance(value, dict) and value.get('kind') == 'member':
            owner = cls._value(value.get('owner'), slots)
            name = value.get('name')
            if isinstance(owner, dict):
                return owner.get(name)
            return getattr(owner, str(name))
        if isinstance(value, dict) and value.get('kind') == 'subscript':
            return cls._value(value.get('owner'), slots)[cls._value(value.get('key'), slots)]
        if isinstance(value, dict) and value.get('kind') == 'unary':
            operand = cls._value(value.get('operand'), slots)
            return {'not': lambda: not operand, 'negative': lambda: -operand, 'positive': lambda: +operand}[value.get('operator')]()
        if isinstance(value, dict) and value.get('kind') == 'boolean':
            values = value.get('values') or []
            if value.get('operator') == 'and':
                return all(bool(cls._value(item, slots)) for item in values)
            return any(bool(cls._value(item, slots)) for item in values)
        if isinstance(value, dict) and value.get('kind') == 'binary':
            left, right = cls._value(value.get('left'), slots), cls._value(value.get('right'), slots)
            operators = {
                'add': lambda: left + right, 'subtract': lambda: left - right,
                'multiply': lambda: left * right, 'divide': lambda: left / right,
                'modulo': lambda: left % right, 'floor_divide': lambda: left // right,
            }
            return operators[value.get('operator')]()
        if isinstance(value, dict) and value.get('kind') == 'compare':
            left = cls._value(value.get('left'), slots)
            operators = value.get('operators') or []
            comparators = value.get('comparators') or []
            for operator, raw_right in zip(operators, comparators, strict=True):
                right = cls._value(raw_right, slots)
                if operator == 'equal':
                    matched = left == right
                elif operator == 'not_equal':
                    matched = left != right
                elif operator == 'less':
                    matched = left < right
                elif operator == 'less_equal':
                    matched = left <= right
                elif operator == 'greater':
                    matched = left > right
                elif operator == 'greater_equal':
                    matched = left >= right
                elif operator == 'in':
                    matched = left in right
                elif operator == 'not_in':
                    matched = left not in right
                elif operator == 'is':
                    matched = left is right
                elif operator == 'is_not':
                    matched = left is not right
                else:
                    matched = False
                if not matched:
                    return False
                left = right
            return True
        if isinstance(value, list):
            return [cls._value(item, slots) for item in value]
        if isinstance(value, dict) and value.get('kind') == 'call' and value.get('function') == '图片资源':
            positional = value.get('positional') or []
            if not positional:
                raise RuntimeFailure('图片资源缺少名称')
            return {'resource_name': cls._value(positional[0], slots)}
        if isinstance(value, dict) and value.get('kind') in {'call', 'expression'}:
            raise RuntimeFailure('此位置的表达式尚不能求值；请使用常量、变量或受支持运算')
        if isinstance(value, dict):
            return {key: cls._value(child, slots) for key, child in value.items()}
        return value

    @classmethod
    def _pure_operation(cls, value: dict[str, Any], slots: dict[str, Any]) -> Any:
        operation_id = str(value.get('operation_id') or '')
        raw_inputs = dict(value.get('inputs') or {})
        evaluated_inputs: dict[str, Any] = {}

        def input_suffix(name: str) -> Any:
            matching_keys = [key for key in raw_inputs if key.endswith(f'.input.{name}')]
            if len(matching_keys) != 1:
                raise RuntimeFailure(
                    f'纯值操作 {operation_id} 缺少或重复输入：{name}',
                    error_id='runtime.operation_input',
                )
            key = matching_keys[0]
            if key not in evaluated_inputs:
                evaluated_inputs[key] = cls._value(raw_inputs[key], slots)
            return evaluated_inputs[key]

        def raw_input(name: str) -> Any:
            matching_keys = [key for key in raw_inputs if key.endswith(f'.input.{name}')]
            if len(matching_keys) != 1:
                raise RuntimeFailure(
                    f'纯值操作 {operation_id} 缺少或重复输入：{name}',
                    error_id='runtime.operation_input',
                )
            return raw_inputs[matching_keys[0]]

        def selector_value(name: str, **bindings: Any) -> Any:
            selector = raw_input(name)
            if not isinstance(selector, dict) or selector.get('kind') != 'selector':
                fail(f'纯值操作 {operation_id} 的 {name} 不是逐项选择器')
            declared = selector.get('bindings') or []
            scoped = dict(slots)
            for binding in declared:
                if not isinstance(binding, dict):
                    fail('逐项选择器绑定无效')
                role = str(binding.get('role') or '')
                symbol_id = str(binding.get('symbol_id') or '')
                if role not in bindings or not symbol_id:
                    fail(f'逐项选择器缺少绑定：{role or "<empty>"}')
                scoped[symbol_id] = bindings[role]
            return cls._value(selector.get('expression'), scoped)

        def cancellation_checkpoint(index_value: int) -> None:
            if index_value % 256:
                return
            checker = slots.get('__cancel_check__')
            if callable(checker) and checker():
                raise RuntimeFailure('纯值集合计算已取消', error_id='runtime.cancelled')

        def fail(message: str, error_id: str = 'runtime.operation_invalid') -> None:
            raise RuntimeFailure(message, error_id=error_id)

        def index(sequence: list[Any], raw: Any, *, allow_end: bool = False) -> int:
            if not isinstance(raw, int) or isinstance(raw, bool):
                fail('列表序号必须是整数')
            upper = len(sequence) if allow_end else len(sequence) - 1
            if raw < 0 or raw > upper:
                fail('列表序号超出范围', 'runtime.collection_index')
            return raw

        def portable_time_pattern(pattern: str, *, parsing: bool = False) -> str:
            replacements = (
                ('yyyy', '%Y'), ('SSS', '%f' if parsing else '__MILLIS__'),
                ('XXX', '%z' if parsing else '__ZONE__'),
                ('MM', '%m'), ('dd', '%d'), ('HH', '%H'),
                ('mm', '%M'), ('ss', '%S'),
            )
            translated = pattern
            for token, replacement in replacements:
                translated = translated.replace(token, replacement)
            if re.search(r'[A-Za-z]', translated.replace('__MILLIS__', '').replace('__ZONE__', '').replace('%Y', '').replace('%f', '').replace('%z', '')
                         .replace('%m', '').replace('%d', '').replace('%H', '').replace('%M', '').replace('%S', '')):
                fail('日期时间格式包含不支持的字母；支持 yyyy MM dd HH mm ss SSS XXX', 'time.pattern_invalid')
            return translated

        def parse_datetime_value(raw: Any) -> datetime:
            try:
                return datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            except ValueError as exc:
                raise RuntimeFailure('日期与时间值无效', error_id='time.value_invalid') from exc

        if operation_id.startswith('core.number_'):
            if operation_id == 'core.number_add.v1':
                return input_suffix('left') + input_suffix('right')
            if operation_id == 'core.number_subtract.v1':
                return input_suffix('left') - input_suffix('right')
            if operation_id == 'core.number_multiply.v1':
                return input_suffix('left') * input_suffix('right')
            if operation_id in {'core.number_divide.v1', 'core.number_modulo.v1'}:
                right = input_suffix('right')
                if right == 0:
                    fail('除数不能为零', 'runtime.divide_by_zero')
                left = input_suffix('left')
                return left / right if operation_id.endswith('divide.v1') else left % right
            if operation_id == 'core.number_min.v1':
                return min(input_suffix('left'), input_suffix('right'))
            if operation_id == 'core.number_max.v1':
                return max(input_suffix('left'), input_suffix('right'))
            if operation_id == 'core.number_clamp.v1':
                number = input_suffix('value')
                minimum, maximum = input_suffix('minimum'), input_suffix('maximum')
                if minimum > maximum:
                    fail('范围下限不能大于上限')
                return min(maximum, max(minimum, number))
            if operation_id == 'core.number_round.v1':
                return round(input_suffix('value'), int(input_suffix('digits')))
            if operation_id == 'core.number_to_int.v1':
                return int(input_suffix('value'))
            if operation_id == 'core.number_to_float.v1':
                return float(input_suffix('value'))
        if operation_id == 'core.value_to_text.v1':
            value = input_suffix('value')
            if isinstance(value, bool):
                return 'true' if value else 'false'
            if isinstance(value, float):
                if not math.isfinite(value):
                    fail('只有有限小数可以转为文本', 'runtime.number_not_finite')
                normalized = format(Decimal(str(value)).normalize(), 'f')
                return '0' if normalized in {'-0', '-0.0'} else normalized
            if isinstance(value, dict):
                if value.get('kind') in {'date', 'datetime', 'time', 'time_of_day'}:
                    return str(value.get('value') or '')
                if value.get('kind') == 'duration':
                    milliseconds = value.get('milliseconds')
                    if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
                        fail('持续时间的毫秒值无效', 'runtime.argument_type')
                    if isinstance(milliseconds, float) and not math.isfinite(milliseconds):
                        fail('只有有限持续时间可以转为文本', 'runtime.number_not_finite')
                    return str(int(milliseconds)) if float(milliseconds).is_integer() else format(Decimal(str(milliseconds)).normalize(), 'f')
                fail('该结构化值不能直接转为文本', 'runtime.argument_type')
            return str(value)
        if operation_id == 'core.text_to_int.v1':
            text_value = str(input_suffix('text')).strip()
            if re.fullmatch(r'[+-]?[0-9]+', text_value) is None:
                return None
            try:
                parsed = int(text_value)
            except ValueError:
                return None
            return parsed if -(2 ** 63) <= parsed <= 2 ** 63 - 1 else None
        if operation_id == 'core.text_to_float.v1':
            text_value = str(input_suffix('text')).strip()
            if re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', text_value) is None:
                return None
            try:
                parsed = float(text_value)
            except ValueError:
                return None
            return parsed if math.isfinite(parsed) else None
        if operation_id == 'core.text_regex_extract.v1':
            try:
                match = re.search(str(input_suffix('pattern')), str(input_suffix('text')))
            except re.error as exc:
                raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
            if match is None:
                return None
            group = input_suffix('group')
            if isinstance(group, bool) or not isinstance(group, int) or group < 0 or group > len(match.groups()):
                fail('正则分组序号超出范围', 'text.regex_group_invalid')
            return match.group(group) or ''
        if operation_id == 'core.text_regex_groups.v1':
            try:
                match = re.search(str(input_suffix('pattern')), str(input_suffix('text')))
            except re.error as exc:
                raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
            return [] if match is None else [item or '' for item in match.groups()]
        if operation_id == 'core.text_extract_first_int.v1':
            match = re.search(r'[+-]?[0-9]+', str(input_suffix('text')))
            if match is None:
                return None
            parsed = int(match.group(0))
            return parsed if -(2 ** 63) <= parsed <= 2 ** 63 - 1 else None
        if operation_id == 'core.text_parse_datetime.v1':
            try:
                parsed = datetime.strptime(
                    str(input_suffix('text')),
                    portable_time_pattern(str(input_suffix('pattern')), parsing=True),
                )
            except ValueError:
                return None
            return parsed.isoformat(timespec='milliseconds' if parsed.microsecond else 'seconds')
        if operation_id in {'core.datetime_add_duration.v1', 'core.datetime_subtract_duration.v1'}:
            parsed = parse_datetime_value(input_suffix('datetime'))
            milliseconds = input_suffix('duration')
            if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
                fail('持续时间必须是毫秒数', 'runtime.argument_type')
            if operation_id == 'core.datetime_subtract_duration.v1':
                milliseconds = -milliseconds
            result = parsed + timedelta(milliseconds=float(milliseconds))
            return result.isoformat(timespec='milliseconds' if result.microsecond else 'seconds')
        if operation_id == 'core.datetime_difference.v1':
            later = parse_datetime_value(input_suffix('later'))
            earlier = parse_datetime_value(input_suffix('earlier'))
            if (later.tzinfo is None) != (earlier.tzinfo is None):
                fail('两个日期与时间必须同时包含或同时不包含时区', 'time.timezone_mismatch')
            return int((later - earlier).total_seconds() * 1000)
        if operation_id == 'core.datetime_format.v1':
            parsed = parse_datetime_value(input_suffix('datetime'))
            rendered = parsed.strftime(portable_time_pattern(str(input_suffix('pattern'))))
            offset = parsed.strftime('%z')
            zone = f'{offset[:3]}:{offset[3:]}' if len(offset) == 5 else offset
            return rendered.replace('__MILLIS__', f'{parsed.microsecond // 1000:03d}').replace('__ZONE__', zone)
        if operation_id == 'core.date_add_days.v1':
            try:
                parsed = datetime.strptime(str(input_suffix('date')), '%Y-%m-%d').date()
            except ValueError as exc:
                raise RuntimeFailure('日期值无效', error_id='time.value_invalid') from exc
            return (parsed + timedelta(days=int(input_suffix('days')))).isoformat()
        if operation_id == 'core.date_difference.v1':
            try:
                later = datetime.strptime(str(input_suffix('later')), '%Y-%m-%d').date()
                earlier = datetime.strptime(str(input_suffix('earlier')), '%Y-%m-%d').date()
            except ValueError as exc:
                raise RuntimeFailure('日期值无效', error_id='time.value_invalid') from exc
            return (later - earlier).days
        if operation_id == 'core.time_add_duration.v1':
            try:
                parsed = datetime.strptime(str(input_suffix('time')), '%H:%M:%S')
            except ValueError as exc:
                raise RuntimeFailure('时间值无效；当前支持 HH:mm:ss', error_id='time.value_invalid') from exc
            milliseconds = input_suffix('duration')
            if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
                fail('持续时间必须是毫秒数', 'runtime.argument_type')
            result = parsed + timedelta(milliseconds=float(milliseconds))
            return result.time().isoformat(timespec='milliseconds' if result.microsecond else 'seconds')
        if operation_id in {
            'core.duration_from_milliseconds.v1', 'core.duration_from_seconds.v1',
            'core.duration_from_minutes.v1',
        }:
            amount = input_suffix('amount')
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
                fail('持续时间数值必须是有限数字', 'runtime.argument_type')
            if amount < 0:
                fail('持续时间不能小于 0', 'runtime.argument_range')
            multiplier = {
                'core.duration_from_milliseconds.v1': 1,
                'core.duration_from_seconds.v1': 1_000,
                'core.duration_from_minutes.v1': 60_000,
            }[operation_id]
            return int(float(amount) * multiplier)
        if operation_id == 'core.duration_poll_count.v1':
            timeout = input_suffix('timeout')
            interval = input_suffix('interval')
            if (
                isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or isinstance(interval, bool) or not isinstance(interval, (int, float))
                or timeout < 0 or interval <= 0
            ):
                fail('轮询超时和间隔配置无效', 'target.invalid_duration')
            return max(1, int(math.ceil(float(timeout) / float(interval))) + 1)
        if operation_id == 'core.text_matches.v1':
            actual = str(input_suffix('actual'))
            expected = str(input_suffix('expected'))
            mode = str(input_suffix('mode'))
            if not expected:
                fail('目标文字不能为空', 'runtime.argument_range')
            if mode == 'exact':
                return actual == expected
            if mode == 'contains':
                return expected in actual
            if mode == 'regex':
                try:
                    return re.search(expected, actual) is not None
                except re.error as exc:
                    raise RuntimeFailure(
                        f'正则表达式无效：{exc}', error_id='text.regex_invalid',
                    ) from exc
            fail('文字匹配方式无效', 'runtime.argument_range')
        if operation_id.startswith('core.text_'):
            if operation_id == 'core.text_join.v1':
                separator = str(input_suffix('separator'))
                values = input_suffix('list')
                if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                    fail('连接文本需要文本列表', 'runtime.argument_type')
                return separator.join(values)
            text = str(input_suffix('text')) if operation_id != 'core.text_concat.v1' else ''
            if operation_id == 'core.text_concat.v1':
                return str(input_suffix('left')) + str(input_suffix('right'))
            if operation_id == 'core.text_replace.v1':
                return text.replace(str(input_suffix('search')), str(input_suffix('replacement')))
            if operation_id == 'core.text_slice.v1':
                return text[int(input_suffix('start')):int(input_suffix('end'))]
            if operation_id == 'core.text_lower.v1':
                return text.lower()
            if operation_id == 'core.text_upper.v1':
                return text.upper()
            if operation_id == 'core.text_trim.v1':
                return text.strip()
            if operation_id == 'core.text_length.v1':
                return len(text)
            if operation_id == 'core.text_split.v1':
                separator = str(input_suffix('separator'))
                if not separator:
                    fail('文本分隔符不能为空', 'text.separator_empty')
                return text.split(separator)
        if operation_id == 'core.optional_has_value.v1':
            return input_suffix('value') is not None
        if operation_id == 'core.optional_default.v1':
            candidate = input_suffix('value')
            return input_suffix('default') if candidate is None else candidate
        if operation_id == 'core.select.v1':
            return input_suffix('when_true') if bool(input_suffix('condition')) else input_suffix('when_false')
        if operation_id == 'core.point_offset.v1':
            point, offset = input_suffix('point'), input_suffix('offset')
            return {
                'kind': 'point',
                'x': point['x'] + offset['x'],
                'y': point['y'] + offset['y'],
            }
        if operation_id == 'core.point_scale.v1':
            point = input_suffix('point')
            scale_x, scale_y = input_suffix('scale_x'), input_suffix('scale_y')
            return {
                **point,
                'kind': 'point',
                'x': point['x'] * scale_x,
                'y': point['y'] * scale_y,
            }
        if operation_id == 'core.rect_center.v1':
            rect = input_suffix('rect')
            return {
                'kind': 'point',
                'x': rect['x'] + rect['width'] / 2,
                'y': rect['y'] + rect['height'] / 2,
            }
        if operation_id == 'core.rect_scale.v1':
            rect = input_suffix('rect')
            scale_x, scale_y = input_suffix('scale_x'), input_suffix('scale_y')
            return {
                **rect,
                'kind': 'rect',
                'x': rect['x'] * scale_x,
                'y': rect['y'] * scale_y,
                'width': rect['width'] * scale_x,
                'height': rect['height'] * scale_y,
            }
        if operation_id == 'core.rect_from_center.v1':
            center = input_suffix('center')
            width, height = input_suffix('width'), input_suffix('height')
            if width < 0 or height < 0:
                fail('区域宽高不能为负数', 'runtime.rect_size_invalid')
            return {
                'kind': 'rect',
                'x': center['x'] - width / 2,
                'y': center['y'] - height / 2,
                'width': width,
                'height': height,
            }
        if operation_id == 'core.color_matches.v1':
            actual, expected = input_suffix('actual'), input_suffix('expected')
            tolerance = input_suffix('tolerance')
            if isinstance(tolerance, bool) or not isinstance(tolerance, int) or not 0 <= tolerance <= 255:
                fail('颜色容差必须为 0 至 255 的整数', 'runtime.color_tolerance_invalid')
            fields = ('red', 'green', 'blue', 'alpha')
            try:
                left = [actual[f'color.field.{field}'] for field in fields]
                right = [expected[f'color.field.{field}'] for field in fields]
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RuntimeFailure('颜色值无效', error_id='runtime.color_invalid') from exc
            if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 255 for item in (*left, *right)):
                fail('颜色通道必须为 0 至 255 的整数', 'runtime.color_invalid')
            return all(abs(a - b) <= tolerance for a, b in zip(left, right, strict=True))
        if operation_id == 'core.file_ref_child.v1':
            from .file_reference_values_v6 import (
                FileReferenceDerivationError,
                derive_file_reference,
            )

            try:
                return derive_file_reference(
                    input_suffix('directory'),
                    input_suffix('relative_path'),
                    str(value.get('result_type') or ''),
                )
            except FileReferenceDerivationError as exc:
                fail(exc.message, exc.error_id)
        if operation_id.startswith('core.list_'):
            items = list(input_suffix('list'))
            if len(items) > 100_000:
                fail('集合超过单次纯值计算安全预算', 'runtime.collection_budget')
            if operation_id == 'core.list_is_empty.v1':
                return not items
            if operation_id == 'core.list_length.v1':
                return len(items)
            if operation_id == 'core.list_contains.v1':
                return input_suffix('value') in items
            if operation_id == 'core.list_first.v1':
                return items[0] if items else None
            if operation_id == 'core.list_last.v1':
                return items[-1] if items else None
            if operation_id == 'core.list_get.v1':
                raw = input_suffix('index')
                return items[raw] if isinstance(raw, int) and 0 <= raw < len(items) else None
            if operation_id == 'core.list_append.v1':
                return [*items, input_suffix('value')]
            if operation_id == 'core.list_prepend.v1':
                return [input_suffix('value'), *items]
            if operation_id == 'core.list_insert.v1':
                position = index(items, input_suffix('index'), allow_end=True)
                return [*items[:position], input_suffix('value'), *items[position:]]
            if operation_id == 'core.list_replace.v1':
                position = index(items, input_suffix('index'))
                return [*items[:position], input_suffix('value'), *items[position + 1:]]
            if operation_id == 'core.list_remove_at.v1':
                position = index(items, input_suffix('index'))
                return [*items[:position], *items[position + 1:]]
            if operation_id == 'core.list_clear.v1':
                return []
            if operation_id == 'core.list_reverse.v1':
                return list(reversed(items))
            if operation_id == 'core.list_slice.v1':
                return items[int(input_suffix('start')):int(input_suffix('end'))]
            if operation_id == 'core.list_concat.v1':
                return [*items, *list(input_suffix('other'))]
            if operation_id == 'core.list_distinct.v1':
                result: list[Any] = []
                for item in items:
                    if item not in result:
                        result.append(item)
                return result
            if operation_id == 'core.list_sum.v1':
                return sum(items)
            if operation_id == 'core.list_average.v1':
                return (sum(items) / len(items)) if items else None
            if operation_id == 'core.list_min.v1':
                return min(items) if items else None
            if operation_id == 'core.list_max.v1':
                return max(items) if items else None
            if operation_id == 'core.list_filter.v1':
                result = []
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if bool(selector_value('predicate', item=item, index=item_index)):
                        result.append(item)
                return result
            if operation_id == 'core.list_map.v1':
                result = []
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    result.append(selector_value('transform', item=item, index=item_index))
                return result
            if operation_id == 'core.list_sort_by.v1':
                decorated = []
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    decorated.append((selector_value('key_selector', item=item, index=item_index), item_index, item))
                try:
                    decorated.sort(key=lambda row: row[0], reverse=bool(input_suffix('descending')))
                except TypeError as exc:
                    raise RuntimeFailure('排序依据包含不可比较的值', error_id='runtime.collection_sort_key') from exc
                return [item for _, _, item in decorated]
            if operation_id == 'core.list_group_by.v1':
                grouped: dict[Any, list[Any]] = {}
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    key = selector_value('key_selector', item=item, index=item_index)
                    try:
                        grouped.setdefault(key, []).append(item)
                    except TypeError as exc:
                        raise RuntimeFailure('分组依据不能作为字典键', error_id='runtime.map_key_invalid') from exc
                return grouped
            if operation_id == 'core.list_flatten.v1':
                result = []
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if not isinstance(item, list):
                        fail('展平操作只接受列表中的列表')
                    if len(result) + len(item) > 100_000:
                        fail('集合超过单次纯值计算安全预算', 'runtime.collection_budget')
                    result.extend(item)
                return result
            if operation_id == 'core.list_zip.v1':
                other = list(input_suffix('other'))
                if len(other) > 100_000:
                    fail('集合超过单次纯值计算安全预算', 'runtime.collection_budget')
                result = []
                for item_index, (left, right) in enumerate(zip(items, other, strict=False)):
                    cancellation_checkpoint(item_index)
                    result.append({
                        'zip_pair.field.left': left,
                        'zip_pair.field.right': right,
                    })
                return result
            if operation_id == 'core.list_find_first.v1':
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if bool(selector_value('predicate', item=item, index=item_index)):
                        return item
                return None
            if operation_id == 'core.list_any.v1':
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if bool(selector_value('predicate', item=item, index=item_index)):
                        return True
                return False
            if operation_id == 'core.list_all.v1':
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if not bool(selector_value('predicate', item=item, index=item_index)):
                        return False
                return True
            if operation_id == 'core.list_count_match.v1':
                count = 0
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    if bool(selector_value('predicate', item=item, index=item_index)):
                        count += 1
                return count
            if operation_id == 'core.list_index_by.v1':
                indexed: dict[Any, Any] = {}
                for item_index, item in enumerate(items):
                    cancellation_checkpoint(item_index)
                    key = selector_value('key_selector', item=item, index=item_index)
                    try:
                        duplicate = key in indexed
                    except TypeError as exc:
                        raise RuntimeFailure('索引依据不能作为字典键', error_id='runtime.map_key_invalid') from exc
                    if duplicate:
                        fail('按依据建立索引时遇到重复键', 'runtime.map_duplicate_key')
                    indexed[key] = item
                return indexed
        if operation_id.startswith('core.map_'):
            source = dict(input_suffix('map'))
            entries_snapshot = list(source.items())
            if len(source) > 100_000:
                fail('集合超过单次纯值计算安全预算', 'runtime.collection_budget')
            if operation_id == 'core.map_has_key.v1':
                return input_suffix('key') in source
            if operation_id == 'core.map_get.v1':
                return source.get(input_suffix('key'))
            if operation_id == 'core.map_set.v1':
                return {**source, input_suffix('key'): input_suffix('value')}
            if operation_id == 'core.map_delete.v1':
                result = dict(source)
                result.pop(input_suffix('key'), None)
                return result
            if operation_id == 'core.map_clear.v1':
                return {}
            if operation_id == 'core.map_keys.v1':
                return list(source.keys())
            if operation_id == 'core.map_values.v1':
                return list(source.values())
            if operation_id == 'core.map_entries.v1':
                return [{'key': key, 'value': item} for key, item in source.items()]
            if operation_id == 'core.map_merge.v1':
                other = dict(input_suffix('other'))
                policy = str(input_suffix('conflict'))
                overlap = source.keys() & other.keys()
                if overlap and policy == 'error':
                    fail('字典合并遇到重复键', 'runtime.map_duplicate_key')
                return ({**other, **source} if policy == 'keep_old' else {**source, **other})
            if operation_id == 'core.map_filter.v1':
                result: dict[Any, Any] = {}
                for item_index, (key, item) in enumerate(entries_snapshot):
                    cancellation_checkpoint(item_index)
                    if bool(selector_value('predicate', key=key, value=item)):
                        result[key] = item
                return result
            if operation_id == 'core.map_map_values.v1':
                result = {}
                for item_index, (key, item) in enumerate(entries_snapshot):
                    cancellation_checkpoint(item_index)
                    result[key] = selector_value('transform', key=key, value=item)
                return result
            if operation_id == 'core.map_group_by.v1':
                grouped: dict[Any, list[dict[str, Any]]] = {}
                for item_index, (key, item) in enumerate(entries_snapshot):
                    cancellation_checkpoint(item_index)
                    group = selector_value('key_selector', key=key, value=item)
                    try:
                        grouped.setdefault(group, []).append({
                            'map_entry.field.key': key,
                            'map_entry.field.value': item,
                        })
                    except TypeError as exc:
                        raise RuntimeFailure('分组依据不能作为字典键', error_id='runtime.map_key_invalid') from exc
                return grouped
        if operation_id == 'core.json_parse_text.v1':
            try:
                return json.loads(str(input_suffix('text')))
            except (TypeError, ValueError):
                return None
        if operation_id == 'core.json_validate_schema.v1':
            source = copy.deepcopy(input_suffix('json'))
            schema = input_suffix('schema')
            try:
                validate_json_schema(source, schema)
            except JsonSchemaDefinitionError as exc:
                raise RuntimeFailure(
                    f'JSON Schema 无效：{exc}', error_id='runtime.json_schema_definition',
                ) from exc
            except JsonSchemaValueError as exc:
                path = ''.join(
                    f'[{part}]' if isinstance(part, int) else f'.{part}'
                    for part in exc.path
                ) or '<root>'
                raise RuntimeFailure(
                    f'JSON 不符合 Schema，位置 {path}：{exc.detail}',
                    error_id='runtime.json_schema_invalid',
                ) from exc
            return source
        if operation_id.startswith('core.json_path_'):
            source = copy.deepcopy(input_suffix('json'))
            path = list(input_suffix('path'))

            def locate(root: Any, *, parent: bool = False) -> tuple[bool, Any, Any]:
                current = root
                limit = path[:-1] if parent else path
                for part in limit:
                    if isinstance(current, dict) and str(part) in current:
                        current = current[str(part)]
                    elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
                        current = current[part]
                    else:
                        return False, None, None
                return True, current, path[-1] if parent and path else None

            if operation_id == 'core.json_path_exists.v1':
                return locate(source)[0]
            if operation_id == 'core.json_path_get.v1':
                found, result, _ = locate(source)
                return result if found else None
            if not path:
                return input_suffix('value') if operation_id.endswith('set.v1') else None
            found, owner, key = locate(source, parent=True)
            if not found:
                return None
            if operation_id == 'core.json_path_set.v1':
                if isinstance(owner, dict):
                    owner[str(key)] = input_suffix('value')
                elif isinstance(owner, list) and isinstance(key, int) and 0 <= key < len(owner):
                    owner[key] = input_suffix('value')
                else:
                    return None
            else:
                if isinstance(owner, dict):
                    owner.pop(str(key), None)
                elif isinstance(owner, list) and isinstance(key, int) and 0 <= key < len(owner):
                    owner.pop(key)
                else:
                    return None
            return source
        raise RuntimeFailure(
            f'纯值操作尚未实现：{operation_id}',
            error_id='runtime.operation_unsupported',
        )

    @staticmethod
    def _target_key(target: dict[str, Any] | None) -> str:
        if not target:
            return ''
        target_id = str(target.get('target_id') or '')
        if target_id:
            return f'target:{target_id}'
        if target.get('type') == 'android_adb':
            return f'adb:{target.get("device_serial") or "auto"}'
        if target.get('type') == 'windows':
            return f'window:{target.get("window_title") or "desktop"}'
        return f'target:{target.get("type") or "unbound"}'

    def _acquire_target(self, session: RuntimeSession, target_key: str) -> None:
        if not target_key:
            return
        with self._lock:
            owner = self._target_owners.get(target_key)
            if owner is not None and owner != session.execution_id:
                raise RuntimeFailure(
                    f'运行目标正在被其他任务占用：{target_key}',
                    error_id='target.busy',
                )
            self._target_owners[target_key] = session.execution_id

    def _release_target(self, session: RuntimeSession, target_key: str) -> None:
        if not target_key:
            return
        with self._lock:
            if self._target_owners.get(target_key) == session.execution_id:
                self._target_owners.pop(target_key, None)

    def start(
        self,
        ecir: dict[str, Any],
        driver: Any = None,
        debug: dict[str, Any] | None = None,
        *,
        target: dict[str, Any] | None = None,
        execution_id: str = '',
        target_driver_factory: Callable[[str, dict[str, Any]], Any] | None = None,
        message_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        options = debug or {}
        project_variables: dict[str, Any] = {}
        project_variable_definitions: dict[str, dict[str, Any]] = {}
        for definition in ecir.get('project_variables') or []:
            variable_id = str(definition.get('variable_id') or '')
            value_type = str(definition.get('value_type') or '')
            if not variable_id or not value_type or variable_id in project_variable_definitions:
                raise RuntimeFailure(
                    '项目变量运行契约缺少稳定 ID、类型或包含重复 ID',
                    error_id='runtime.project_variable_contract',
                )
            default_value = self._value(
                definition.get('default_value'),
                {'__project__': {}},
            )
            if not runtime_project_value_conforms(default_value, value_type):
                raise RuntimeFailure(
                    f'项目变量“{definition.get("display_name") or variable_id}”默认值类型无效',
                    error_id='runtime.project_variable_default',
                )
            try:
                validate_runtime_constraints(
                    default_value,
                    dict(definition.get('constraints') or {}),
                )
            except ValueError as exc:
                raise RuntimeFailure(
                    f'项目变量“{definition.get("display_name") or variable_id}”默认值无效：{exc}',
                    error_id='runtime.project_variable_default',
                ) from exc
            project_variable_definitions[variable_id] = copy.deepcopy(definition)
            project_variables[variable_id] = copy.deepcopy(default_value)
        overrides = dict(ecir.get('project_variable_overrides') or {})
        unknown_overrides = sorted(set(overrides) - set(project_variable_definitions))
        if unknown_overrides:
            raise RuntimeFailure(
                f'项目变量初始覆盖不存在：{unknown_overrides[0]}',
                error_id='runtime.project_variable_override_unknown',
            )
        for variable_id, encoded in overrides.items():
            definition = project_variable_definitions[variable_id]
            value = self._value(encoded, {'__project__': {}})
            if not runtime_project_value_conforms(value, str(definition['value_type'])):
                raise RuntimeFailure(
                    f'项目变量“{definition.get("display_name") or variable_id}”初始覆盖类型无效',
                    error_id='runtime.project_variable_override_type',
                )
            try:
                validate_runtime_constraints(value, dict(definition.get('constraints') or {}))
            except ValueError as exc:
                raise RuntimeFailure(
                    f'项目变量“{definition.get("display_name") or variable_id}”初始覆盖无效：{exc}',
                    error_id='runtime.project_variable_override_constraint',
                ) from exc
            project_variables[variable_id] = copy.deepcopy(value)
        effective_target = target or (
            getattr(driver, 'target', None) if driver is not None else None
        )
        if effective_target is None and ecir.get('default_target_id'):
            effective_target = next((
                item for item in (ecir.get('targets') or [])
                if isinstance(item, dict)
                and str(item.get('target_id') or '') == str(ecir.get('default_target_id'))
            ), None)
        session = RuntimeSession(
            execution_id or f'execution_{uuid.uuid4().hex}',
            breakpoints={str(item) for item in (options.get('breakpoints') or []) if str(item)},
            pause_requested=bool(options.get('pause_on_start')),
            project_path=str(ecir.get('project_path') or getattr(driver, 'project_path', '') or ''),
            runtime_data_directory=str(ecir.get('runtime_data_directory') or ''),
            dangerous_confirmations={
                str(item.get('statement_id') or ''): copy.deepcopy(item)
                for item in (
                    options.get('dangerous_operation_confirmations')
                    or ecir.get('dangerous_operation_confirmations')
                    or []
                )
                if isinstance(item, dict) and str(item.get('statement_id') or '')
            },
            hard_timeout_seconds=max(0.0, float(options.get('hard_timeout_ms') or 0)) / 1000,
            target_key=self._target_key(effective_target),
            project_variables=project_variables,
            project_variable_definitions=project_variable_definitions,
            local_variable_definitions=copy.deepcopy(
                dict((ecir.get('debug_map') or {}).get('symbols') or {})
            ),
            message_context=copy.deepcopy(message_context or {}),
        )
        session.events = deque(maxlen=self._event_buffer_size)
        if session._resume_gate is not None:
            session._resume_gate.set()
        with self._lock:
            self._prune_sessions(reserve_slots=1)
            if session.target_key and session.target_key in self._target_owners:
                raise RuntimeFailure(f'运行目标正在被其他任务占用：{session.target_key}')
            if session.target_key:
                self._target_owners[session.target_key] = session.execution_id
            self._sessions[session.execution_id] = session
        if self._use_worker_process:
            if driver is not None:
                with self._lock:
                    self._sessions.pop(session.execution_id, None)
                    self._target_owners.pop(session.target_key, None)
                raise RuntimeFailure('隔离运行器不接受主进程驱动对象；请传递目标配置')
            return self._start_worker(session, ecir, target, options)
        self._prepare_event_log(session)
        threading.Thread(
            target=self._run,
            args=(session, ecir, driver, target_driver_factory),
            name=f'easycode-vnext-{session.execution_id[-8:]}', daemon=True,
        ).start()
        return session.snapshot()

    def _start_worker(
        self,
        session: RuntimeSession,
        ecir: dict[str, Any],
        target: dict[str, Any] | None,
        debug: dict[str, Any],
    ) -> dict[str, Any]:
        from .execution_worker import spawn_vnext_worker

        try:
            proxy = spawn_vnext_worker({
                'execution_id': session.execution_id,
                'project_path': session.project_path,
                'ecir': ecir,
                'target': target,
                'debug': debug,
                'message_context': copy.deepcopy(session.message_context),
            })
        except Exception as exc:
            with self._lock:
                self._sessions.pop(session.execution_id, None)
                self._target_owners.pop(session.target_key, None)
            raise RuntimeFailure(f'执行 Worker 启动失败：{exc}') from exc
        session._worker_proxy = proxy
        session.worker_pid = int(proxy.process.pid or 0)
        threading.Thread(
            target=self._follow_worker,
            args=(session, proxy),
            name=f'easycode-vnext-monitor-{session.execution_id[-8:]}',
            daemon=True,
        ).start()
        return session.snapshot()

    def _apply_worker_state(self, session: RuntimeSession, snapshot: dict[str, Any]) -> None:
        with self._lock:
            for name in (
                'status', 'started_at', 'finished_at', 'error', 'error_id', 'error_details',
                'current_instruction_id', 'current_listener_id', 'current_message_id',
            ):
                if name in snapshot:
                    setattr(session, name, snapshot[name])
            session.current_source = dict(snapshot.get('current_source') or {})
            session.variables = dict(snapshot.get('variables') or {})
            session.project_variables = copy.deepcopy(snapshot.get('project_variables') or {})
            session.breakpoints = {str(item) for item in snapshot.get('breakpoints') or []}
            session._call_stack = copy.deepcopy(snapshot.get('call_stack') or [])
            self._events_changed.notify_all()

    def _follow_worker(self, session: RuntimeSession, proxy: Any) -> None:
        last_message = time.monotonic()
        terminal_received = False
        failure = ''
        try:
            while True:
                message = proxy.receive(0.25)
                now = time.monotonic()
                if message:
                    last_message = now
                    kind = str(message.get('type') or '')
                    if kind == 'ready':
                        session.worker_started = True
                        session.event_log_path = str(message.get('event_log_path') or '')
                        self._apply_worker_state(session, message.get('snapshot') or {})
                    elif kind == 'event':
                        self._worker_event(session, message.get('event') or {})
                    elif kind == 'state':
                        self._apply_worker_state(session, message.get('snapshot') or {})
                    elif kind == 'final':
                        self._apply_worker_state(session, message.get('snapshot') or {})
                        session.diagnostic_bundle = str(message.get('diagnostic_bundle') or '')
                        session.failure_frame = str(message.get('failure_frame') or '')
                        session.event_log_path = str(message.get('event_log_path') or session.event_log_path)
                        terminal_received = True
                        break
                    elif kind == 'fatal':
                        failure = str(message.get('error') or '执行 Worker 发生未知错误')
                        break
                if session.hard_timeout_seconds and now - proxy.started_at >= session.hard_timeout_seconds:
                    failure = f'执行超过硬超时 {session.hard_timeout_seconds:g} 秒，Worker 已终止'
                    proxy.terminate_tree()
                    break
                if session.cancel_deadline and now >= session.cancel_deadline and proxy.is_alive():
                    failure = '执行取消超时，Worker 已强制终止'
                    proxy.terminate_tree()
                    break
                if not session.worker_started and now - proxy.started_at > 20:
                    failure = '执行 Worker 初始化超时'
                    proxy.terminate_tree()
                    break
                if session.worker_started and now - last_message > 15:
                    failure = '执行 Worker 心跳超时'
                    proxy.terminate_tree()
                    break
                if not proxy.is_alive():
                    trailing = proxy.receive(0.1)
                    if trailing and trailing.get('type') == 'final':
                        self._apply_worker_state(session, trailing.get('snapshot') or {})
                        session.diagnostic_bundle = str(trailing.get('diagnostic_bundle') or '')
                        session.failure_frame = str(trailing.get('failure_frame') or '')
                        session.event_log_path = str(trailing.get('event_log_path') or session.event_log_path)
                        terminal_received = True
                    elif not terminal_received:
                        failure = f'执行 Worker 异常退出（代码 {proxy.process.exitcode}）'
                    break
        finally:
            if failure and session.status not in {'completed', 'failed', 'cancelled'}:
                session.status = 'cancelled' if session.cancel_requested else 'failed'
                session.error = failure
                context = ''
                if session.current_listener_id or session.current_message_id:
                    context = (
                        f'；listener_id={session.current_listener_id or "unknown"}'
                        f' message_id={session.current_message_id or "unknown"}'
                    )
                if session._call_stack:
                    context += '；call_stack=' + ' -> '.join(
                        str(item.get('function_id') or 'unknown')
                        for item in session._call_stack
                    )
                self._event(
                    session,
                    'error' if session.status == 'failed' else 'warning',
                    'worker',
                    failure + context,
                )
                session.finished_at = self._now()
            session.finished_monotonic = time.monotonic()
            with self._events_changed:
                self._target_owners.pop(session.target_key, None)
                self._events_changed.notify_all()
            proxy.join(timeout=1.0)
            if proxy.is_alive():
                proxy.terminate_tree()
                proxy.join(timeout=1.0)
            proxy.close()
            # A completed session only needs the copied worker PID and terminal
            # snapshot.  Retaining the closed proxy keeps multiprocessing
            # synchronization wrappers reachable for the lifetime of the
            # session and leaks one Windows handle per completed execution in a
            # long-lived Player process.
            with self._lock:
                if session._worker_proxy is proxy:
                    session._worker_proxy = None
                # Pause/resume is impossible after terminal state. Keeping this
                # Event with every retained history session leaks one Windows
                # kernel handle per completed run.
                session._resume_gate = None

    def _checkpoint(
        self,
        session: RuntimeSession,
        instruction: dict[str, Any],
        slots: dict[str, Any],
        functions: dict[str, dict[str, Any]] | None = None,
        depth: int = 0,
        driver: Any = None,
        *,
        allow_debug_break: bool = True,
    ) -> None:
        instruction_id = str(instruction.get('instruction_id') or '')
        should_pause = session.pause_requested or (
            allow_debug_break
            and (
                session.pause_after_instruction
                or instruction_id in session.breakpoints
            )
        )
        if allow_debug_break:
            session.pause_after_instruction = False
        if should_pause:
            session.pause_requested = False
            session.status = 'paused'
            session.current_instruction_id = instruction_id
            session.current_source = dict(instruction.get('source') or {})
            session.variables = {
                key: value for key, value in slots.items() if not key.startswith('__')
            }
            if session._resume_gate is None:
                raise RuntimeFailure('运行会话的暂停状态已结束')
            session._resume_gate.clear()
            self._event(
                session,
                'info',
                'debug',
                f'已暂停：{instruction_id or "当前语句"}',
                instruction_id,
            )
            while not session.cancel_requested and not session._resume_gate.wait(0.05):
                pass
            if session.cancel_requested:
                session.status = 'cancelled'
                return
            session.status = 'running'
        if (
            not session.cancel_requested
            and functions is not None
            and session._listeners
            and not session._dispatching_listener
        ):
            self._dispatch_ready_listeners(session, functions, depth, driver)
            if not session.current_listener_id:
                session.current_instruction_id = instruction_id
                session.current_source = dict(instruction.get('source') or {})
                session.variables = {
                    key: value for key, value in slots.items() if not key.startswith('__')
                }

    def _register_listener(
        self,
        session: RuntimeSession,
        instruction: dict[str, Any],
        arguments: dict[str, Any],
        slots: dict[str, Any],
        functions: dict[str, dict[str, Any]],
    ) -> None:
        from .message_runtime_v6 import MessageRuntimeV6

        if not session.message_context:
            raise RuntimeFailure(
                '消息监听需要稳定运行实例身份',
                error_id='message.instance_unknown',
            )
        listener_id = str(instruction.get('instruction_id') or '')
        event_source = dict(arguments.get('event_source') or {})
        receive_slot = str(arguments.get('receive_slot') or '')
        handler_function_id = str(arguments.get('handler_function_id') or '')
        dispatch = dict(arguments.get('dispatch') or {})
        if (
            not listener_id
            or event_source.get('kind') != 'message'
            or not receive_slot
            or not handler_function_id
            or handler_function_id not in functions
            or not all(dispatch.get(name) is True for name in (
                'serial', 'fifo', 'safe_checkpoint',
            ))
        ):
            raise RuntimeFailure(
                '消息监听运行契约无效',
                error_id='runtime.listener_contract_invalid',
            )
        if session._message_runtime is None:
            session._message_runtime = MessageRuntimeV6(
                session.message_context.get('database_path') or None,
                lan_root=session.message_context.get('lan_root') or None,
            )
        name = self._value(event_source.get('name'), slots)
        sender = (
            self._value(event_source.get('sender'), slots)
            if event_source.get('sender') is not None else None
        )
        # A zero-limit peek performs all identity/name/sender validation without
        # evaluating the listener condition or touching queue state.
        session._message_runtime._peek_receive_candidates(
            session.message_context,
            name,
            sender,
            limit=0,
        )
        registration = _ListenerRegistration(
            listener_id=listener_id,
            instruction_id=listener_id,
            name=str(name),
            sender=copy.deepcopy(sender),
            receive_slot=receive_slot,
            condition=copy.deepcopy(arguments.get('condition')),
            handler_function_id=handler_function_id,
            handler_arguments=copy.deepcopy(dict(arguments.get('handler_arguments') or {})),
            scope_slots=slots,
        )
        replaced = listener_id in session._listeners
        session._listeners[listener_id] = registration
        self._event(
            session,
            'info',
            'message',
            f'监听器已{ "更新" if replaced else "注册" }：listener_id={listener_id}',
            listener_id,
        )

    def _dispatch_ready_listeners(
        self,
        session: RuntimeSession,
        functions: dict[str, dict[str, Any]],
        depth: int,
        driver: Any,
    ) -> None:
        if session._message_runtime is None or not session.message_context:
            return
        cursor = session._message_runtime._receive_snapshot_cursor(
            session.message_context,
        )
        if cursor <= 0:
            return
        for registration in tuple(session._listeners.values()):
            while True:
                if session.cancel_requested:
                    session.status = 'cancelled'
                    return
                candidates = session._message_runtime._peek_receive_candidates(
                    session.message_context,
                    registration.name,
                    registration.sender,
                    max_rowid=cursor,
                    limit=1,
                )
                if not candidates:
                    break
                candidate = candidates[0]
                event_slots = dict(registration.scope_slots)
                event_slots['__project__'] = session.project_variables
                event_slots[registration.receive_slot] = candidate
                if registration.condition is not None and not bool(
                    self._value(registration.condition, event_slots)
                ):
                    # Preserve FIFO: a blocked head candidate prevents later
                    # candidates for this listener from being overtaken.
                    break
                claimed = session._message_runtime._claim_receive_candidate(
                    session.message_context,
                    str(candidate.get('message_id') or ''),
                    expected_name=registration.name,
                    expected_sender=registration.sender,
                )
                if claimed is None:
                    continue
                event_slots[registration.receive_slot] = claimed
                message_id = str(claimed.get('message_id') or '')
                session._failed_listener_id = ''
                session._failed_message_id = ''
                session.current_listener_id = registration.listener_id
                session.current_message_id = message_id
                self._event(
                    session,
                    'info',
                    'message',
                    f'监听器接手消息：listener_id={registration.listener_id} '
                    f'message_id={message_id}',
                    registration.instruction_id,
                )
                session._dispatching_listener = True
                try:
                    call_arguments = {
                        parameter_id: self._value(value, event_slots)
                        for parameter_id, value in registration.handler_arguments.items()
                    }
                    self._execute_function(
                        session,
                        registration.handler_function_id,
                        functions,
                        call_arguments,
                        depth + 1,
                        driver,
                    )
                    if session.cancel_requested or session.status == 'cancelled':
                        self._event(
                            session,
                            'warning',
                            'message',
                            f'监听处理被取消：listener_id={registration.listener_id} '
                            f'message_id={message_id}',
                            registration.instruction_id,
                        )
                        return
                    self._event(
                        session,
                        'info',
                        'message',
                        f'监听处理完成：listener_id={registration.listener_id} '
                        f'message_id={message_id}',
                        registration.instruction_id,
                    )
                except Exception:
                    session._failed_listener_id = registration.listener_id
                    session._failed_message_id = message_id
                    self._event(
                        session,
                        'error',
                        'message',
                        f'监听处理失败：listener_id={registration.listener_id} '
                        f'message_id={message_id}',
                        registration.instruction_id,
                    )
                    session.current_listener_id = ''
                    session.current_message_id = ''
                    raise
                finally:
                    session._dispatching_listener = False
                session.current_listener_id = ''
                session.current_message_id = ''

    def _run(
        self,
        session: RuntimeSession,
        ecir: dict[str, Any],
        driver: Any = None,
        target_driver_factory: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        session.status, session.started_at = 'running', self._now()
        self._event(session, 'info', 'runtime', '任务开始')
        target_manager: _TargetScopeManager | None = None
        try:
            if driver is None and ecir.get('default_target_id'):
                default_target_id = str(ecir.get('default_target_id') or '')
                default_target = next((
                    item for item in (ecir.get('targets') or [])
                    if isinstance(item, dict)
                    and str(item.get('target_id') or '') == default_target_id
                ), None)
                if default_target is None:
                    raise RuntimeFailure(
                        f'默认目标引用已失效：{default_target_id}',
                        error_id='target.reference_missing',
                    )
                factory = target_driver_factory
                if factory is None:
                    from .target_runtime import create_target_driver

                    factory = create_target_driver
                driver = factory(str(ecir.get('project_path') or ''), default_target)
                if driver is None:
                    raise RuntimeFailure(
                        f'默认目标没有可用驱动：{default_target_id}',
                        error_id='target.driver_unavailable',
                    )
                driver.capture_frame()
            target_manager = _TargetScopeManager(
                self, session, ecir, driver, target_driver_factory,
            )
            functions = {item['function_id']: item for item in (ecir.get('functions') or [])}
            entry = str(ecir.get('entry_function_id') or '')
            entry_arguments = (ecir.get('function_arguments') or {}).get(entry) or {}
            self._execute_function(
                session, entry, functions, dict(entry_arguments), 0, target_manager,
            )
            if session.status == 'cancelled':
                return
            session.status = 'completed'
            self._event(session, 'info', 'runtime', '任务完成')
        except Exception as exc:
            if session.cancel_requested or getattr(exc, 'error_id', '') == 'runtime.cancelled':
                session.status = 'cancelled'
                session.error = ''
                session.error_id = 'runtime.cancelled'
                self._event(
                    session, 'warning', 'runtime', '任务已取消',
                    session.current_instruction_id,
                )
                return
            session.status, session.error = 'failed', str(exc)
            session.error_id = str(getattr(exc, 'error_id', 'runtime.error'))
            session.error_details = self._safe_diagnostic_value(getattr(exc, 'details', None))
            self._event(
                session, 'error', 'runtime', str(exc), session.current_instruction_id,
            )
            self._create_diagnostics(session, target_manager or driver)
        finally:
            if target_manager is not None:
                target_manager.close()
            elif driver is not None and hasattr(driver, 'close'):
                with contextlib.suppress(Exception):
                    driver.close()
            session.finished_at = self._now()
            session.finished_monotonic = time.monotonic()
            self._close_event_log(session)
            session._resume_gate = None
            with self._events_changed:
                self._target_owners.pop(session.target_key, None)
                self._events_changed.notify_all()

    def _execute_function(self, session: RuntimeSession, function_id: str, functions: dict[str, dict[str, Any]], arguments: dict[str, Any], depth: int, driver: Any) -> Any:
        if depth > 100:
            raise RuntimeFailure(
                '项目函数调用深度超过 100，可能存在无限递归',
                error_id='runtime.call_depth_exceeded',
            )
        session._call_stack.append({
            'function_id': function_id,
            'depth': depth,
        })
        try:
            return self._execute_function_body(
                session, function_id, functions, arguments, depth, driver,
            )
        except Exception as exc:
            failure_stack = copy.deepcopy(
                getattr(exc, '_easycode_call_stack', session._call_stack)
            )
            session._failure_call_stack = failure_stack
            with contextlib.suppress(Exception):
                exc._easycode_call_stack = failure_stack
            raise
        finally:
            session._call_stack.pop()

    def _execute_function_body(self, session: RuntimeSession, function_id: str, functions: dict[str, dict[str, Any]], arguments: dict[str, Any], depth: int, driver: Any) -> Any:
        definition = functions.get(function_id)
        if definition is None:
            raise RuntimeFailure(f'项目函数未链接：{function_id}')
        parameter_definitions = [
            item for item in (definition.get('parameter_definitions') or [])
            if isinstance(item, dict)
        ]
        slots: dict[str, Any] = {
            '__project__': session.project_variables,
            '__cancel_check__': lambda: session.cancel_requested,
        }
        accepted_keys: set[str] = set()
        for parameter in parameter_definitions:
            parameter_id = str(parameter.get('parameter_id') or '')
            name = str(parameter.get('name') or '')
            if not parameter_id or not name:
                raise RuntimeFailure(
                    f'函数“{definition.get("name") or function_id}”的参数定义缺少稳定 ID 或局部符号',
                    error_id='runtime.function_contract_invalid',
                )
            accepted_keys.add(parameter_id)
            if parameter_id in arguments:
                value = self._value(arguments[parameter_id], slots)
            else:
                if not parameter.get('required', True):
                    value = self._value(parameter.get('default'), slots)
                else:
                    raise RuntimeFailure(
                        f'函数“{definition.get("name") or function_id}”缺少必填参数：{parameter.get("display_name") or name}',
                        error_id='runtime.argument_missing',
                    )
            value_type = str(parameter.get('value_type') or 'any')
            if not _runtime_value_conforms(value, value_type):
                raise RuntimeFailure(
                    f'函数“{definition.get("name") or function_id}”的参数“{parameter.get("display_name") or name}”需要 {value_type}',
                    error_id='runtime.argument_type',
                )
            slots[name] = value
        unknown = sorted(set(arguments) - accepted_keys)
        if unknown:
            raise RuntimeFailure(
                f'函数“{definition.get("name") or function_id}”收到未声明参数：{"、".join(unknown)}',
                error_id='runtime.argument_unknown',
            )
        return_type = str(definition.get('return_type') or 'any')
        try:
            self._execute_block(session, definition.get('instructions') or [], slots, functions, depth, driver)
        except _ReturnSignal as signal:
            conforms = (
                signal.value is None and return_type in {'null', 'unit'}
            ) or _runtime_value_conforms(signal.value, return_type)
            if not conforms:
                raise RuntimeFailure(
                    f'函数“{definition.get("name") or function_id}”返回值不符合 {return_type}'
                ) from None
            return signal.value
        if session.cancel_requested or session.status == 'cancelled':
            return None
        if return_type not in {'null', 'unit'} and not _runtime_value_conforms(None, return_type):
            raise RuntimeFailure(
                f'函数“{definition.get("name") or function_id}”声明返回 {return_type}，但执行路径没有返回值'
            )
        return None

    def _execute_block(self, session: RuntimeSession, instructions: list[dict[str, Any]], slots: dict[str, Any], functions: dict[str, dict[str, Any]], depth: int, driver: Any) -> None:
        """Execute one structured block; returns use an internal signal."""

        for instruction in instructions:
            if session.cancel_requested:
                session.status = 'cancelled'
                self._event(session, 'warning', 'runtime', '任务已取消')
                return
            self._checkpoint(
                session, instruction, slots, functions, depth, driver,
            )
            if session.cancel_requested:
                session.status = 'cancelled'
                return
            opcode = instruction.get('opcode')
            instruction_id = str(instruction.get('instruction_id') or '')
            session.current_instruction_id = instruction_id
            session.current_source = dict(instruction.get('source') or {})
            arguments = instruction.get('arguments') or {}
            if opcode == 'log.write':
                result = None
                level = str(self._value(
                    arguments.get('official.log.output.parameter.level'),
                    slots,
                ) or 'info')
                if level not in {'info', 'warning', 'error'}:
                    raise RuntimeFailure('日志.输出 的级别必须是信息、警告或错误')
                category = str(self._value(
                    arguments.get('official.log.output.parameter.category'),
                    slots,
                ) or 'script').strip() or 'script'
                self._event(
                    session,
                    level,
                    category,
                    str(self._value(
                        arguments.get('official.log.output.parameter.content'),
                        slots,
                    )),
                    instruction_id,
                )
            elif opcode == 'wait.duration':
                result = None
                milliseconds = self._value(
                    arguments.get('official.wait.duration.parameter.duration'),
                    slots,
                )
                if not isinstance(milliseconds, (int, float)) or isinstance(milliseconds, bool) or milliseconds < 0:
                    raise RuntimeFailure('等待.持续 的时长必须是非负持续时间')
                deadline = time.monotonic() + float(milliseconds) / 1000
                while time.monotonic() < deadline:
                    self._checkpoint(
                        session, instruction, slots, functions, depth, driver,
                        allow_debug_break=False,
                    )
                    if session.cancel_requested:
                        session.status = 'cancelled'
                        self._event(session, 'warning', 'runtime', '任务已取消', instruction_id)
                        return
                    time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            elif opcode == 'wait.until':
                result = None
                target = _resolve_wait_target(
                    self._value(
                        arguments.get('official.wait.until.parameter.time'),
                        slots,
                    ),
                    str(self._value(
                        arguments.get('official.wait.until.parameter.past_policy'),
                        slots,
                    ) or 'next_day'),
                )
                self._event(
                    session, 'info', 'script',
                    f'等待到 {target.isoformat(timespec="seconds")}', instruction_id,
                )
                while True:
                    remaining = (target - datetime.now().astimezone()).total_seconds()
                    if remaining <= 0:
                        break
                    self._checkpoint(
                        session, instruction, slots, functions, depth, driver,
                        allow_debug_break=False,
                    )
                    if session.cancel_requested:
                        session.status = 'cancelled'
                        self._event(session, 'warning', 'runtime', '任务已取消', instruction_id)
                        return
                    time.sleep(min(0.05, remaining))
            elif opcode == 'random.integer':
                minimum = self._value(
                    arguments.get('official.random.integer.parameter.minimum', 0),
                    slots,
                )
                maximum = self._value(
                    arguments.get('official.random.integer.parameter.maximum', 100),
                    slots,
                )
                if (
                    not isinstance(minimum, int)
                    or isinstance(minimum, bool)
                    or not isinstance(maximum, int)
                    or isinstance(maximum, bool)
                ):
                    raise RuntimeFailure(
                        '随机.整数 的最小值和最大值必须是整数',
                        error_id='random.range_invalid',
                    )
                if minimum > maximum:
                    raise RuntimeFailure(
                        '随机.整数 的最小值不能大于最大值',
                        error_id='random.range_invalid',
                    )
                result = random.SystemRandom().randint(minimum, maximum)
            elif opcode == 'time.now':
                requested_timezone = self._value(
                    arguments.get('official.time.now.parameter.timezone'),
                    slots,
                )
                if requested_timezone is None or str(requested_timezone).strip() == '':
                    now = datetime.now().astimezone()
                else:
                    timezone_name = str(requested_timezone).strip()
                    try:
                        selected_timezone = (
                            timezone.utc
                            if timezone_name.upper() in {'UTC', 'Z'}
                            else ZoneInfo(timezone_name)
                        )
                    except (ZoneInfoNotFoundError, ValueError) as exc:
                        raise RuntimeFailure(
                            f'时间.现在 无法使用时区：{timezone_name}',
                            error_id='time.timezone_invalid',
                        ) from exc
                    now = datetime.now(selected_timezone)
                result = now.isoformat(timespec='milliseconds')
            elif opcode == 'time.today':
                requested_timezone = self._value(
                    arguments.get('official.time.today.parameter.timezone'),
                    slots,
                )
                if requested_timezone is None or str(requested_timezone).strip() == '':
                    today = datetime.now().astimezone().date()
                else:
                    timezone_name = str(requested_timezone).strip()
                    try:
                        selected_timezone = (
                            timezone.utc
                            if timezone_name.upper() in {'UTC', 'Z'}
                            else ZoneInfo(timezone_name)
                        )
                    except (ZoneInfoNotFoundError, ValueError) as exc:
                        raise RuntimeFailure(
                            f'时间.今天 无法使用时区：{timezone_name}',
                            error_id='time.timezone_invalid',
                        ) from exc
                    today = datetime.now(selected_timezone).date()
                result = today.isoformat()
            elif opcode == 'project.data_directory':
                from .file_runtime_v6 import windows_directory_reference

                data_directory = session.runtime_data_directory
                if not data_directory:
                    if not session.project_path:
                        raise RuntimeFailure(
                            '项目.数据目录缺少运行宿主目录',
                            error_id='file.invalid_reference',
                        )
                    data_directory = os.path.join(session.project_path, '.easycode', 'data')
                data_directory = os.path.realpath(os.path.abspath(data_directory))
                try:
                    os.makedirs(data_directory, exist_ok=True)
                except OSError as exc:
                    raise RuntimeFailure(
                        f'项目数据目录不可用：{exc}',
                        error_id='file.write_failed',
                    ) from exc
                result = windows_directory_reference(
                    data_directory,
                    data_directory,
                    access=('read', 'list', 'create', 'delete_empty'),
                    authorization_root_id=(
                        'project-data:'
                        + hashlib.sha256(
                            os.path.normcase(data_directory).encode('utf-8')
                        ).hexdigest()
                    ),
                    source='project_data',
                )
            elif opcode == 'data.assign':
                result = self._value(arguments.get('value'), slots)
            elif opcode in {'data.assign_local', 'data.assign_project'}:
                result = self._value(arguments.get('value'), slots)
                target = arguments.get('target') or {}
                if opcode == 'data.assign_local':
                    symbol_id = str(target.get('symbol_id') or '')
                    if not symbol_id:
                        raise RuntimeFailure('局部赋值缺少稳定变量 ID')
                    slots[symbol_id] = result
                else:
                    variable_id = str(target.get('variable_id') or '')
                    if not variable_id:
                        raise RuntimeFailure('项目赋值缺少稳定变量 ID')
                    definition = session.project_variable_definitions.get(variable_id)
                    if definition is None:
                        raise RuntimeFailure(
                            f'项目变量不存在：{variable_id}',
                            error_id='runtime.project_variable_unknown',
                        )
                    if not runtime_project_value_conforms(
                        result,
                        str(definition.get('value_type') or ''),
                    ):
                        raise RuntimeFailure(
                            f'项目变量“{definition.get("display_name") or variable_id}”赋值类型无效',
                            error_id='runtime.project_variable_assignment_type',
                        )
                    try:
                        validate_runtime_constraints(
                            result,
                            dict(definition.get('constraints') or {}),
                        )
                    except ValueError as exc:
                        raise RuntimeFailure(
                            f'项目变量“{definition.get("display_name") or variable_id}”赋值违反约束：{exc}',
                            error_id='runtime.project_variable_assignment_constraint',
                        ) from exc
                    session.project_variables[variable_id] = copy.deepcopy(result)
            elif opcode == 'call.project':
                call_arguments = {name: self._value(value, slots) for name, value in arguments.items()}
                result = self._execute_function(
                    session, str(instruction.get('callee_function_id') or ''), functions,
                    call_arguments, depth + 1, driver,
                )
            elif opcode == 'call.extension':
                call_arguments = {name: self._value(value, slots) for name, value in arguments.items()}
                extension_arguments = (
                    session.project_path,
                    str(instruction.get('callee_function_id') or ''),
                    call_arguments,
                    slots,
                    lambda: session.cancel_requested,
                    lambda level, message, _instruction_id=instruction_id: self._event(
                        session, level, 'extension', message, _instruction_id,
                    ),
                )
                if os.path.isfile(os.path.join(session.project_path, 'runtime', 'easycode.lock')):
                    from .extension_runtime_v6 import invoke_published_extension

                    result = invoke_published_extension(*extension_arguments)
                else:
                    # IDE source-mode execution retains the development
                    # registry.  Published Player roots never take this path,
                    # and the module is excluded from the frozen manifest.
                    from .extensions import VNextExtensionRegistry

                    result = VNextExtensionRegistry.invoke(*extension_arguments)
            elif opcode == 'control.if':
                branch = None
                if bool(self._value(arguments.get('condition'), slots)):
                    branch = arguments.get('then')
                else:
                    for candidate in arguments.get('additional_branches') or []:
                        if bool(self._value(candidate.get('condition'), slots)):
                            branch = candidate.get('body')
                            break
                    if branch is None:
                        branch = arguments.get('otherwise')
                self._execute_block(session, branch or [], slots, functions, depth, driver)
                result = None
            elif opcode == 'control.repeat':
                count = self._value(arguments.get('source', arguments.get('count')), slots)
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    raise RuntimeFailure('重复次数必须是非负整数')
                result = None
                for _ in range(count):
                    try:
                        self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif opcode == 'control.while':
                result = None
                iterations = 0
                condition = arguments.get('source', arguments.get('condition'))
                while bool(self._value(condition, slots)):
                    if session.cancel_requested:
                        session.status = 'cancelled'
                        return
                    iterations += 1
                    if iterations > 1_000_000:
                        raise RuntimeFailure('循环超过 1000000 次，已启动安全保护')
                    try:
                        self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif opcode == 'control.for_each':
                result = None
                iterable = self._value(arguments.get('source', arguments.get('iterable')), slots)
                if arguments.get('snapshot'):
                    iterable = list(iterable)
                bindings = arguments.get('bindings') or {}
                item_binding = bindings.get('item') or {}
                index_binding = bindings.get('index') or {}
                target = str(item_binding.get('symbol_id') or arguments.get('target') or '')
                if not target:
                    raise RuntimeFailure('对于循环缺少项变量')
                try:
                    iterator = iter(iterable)
                except TypeError as exc:
                    raise RuntimeFailure('对于循环的值不可迭代') from exc
                for index, item in enumerate(iterator):
                    if index >= 1_000_000:
                        raise RuntimeFailure('对于循环超过 1000000 项，已启动安全保护')
                    slots[target] = item
                    if index_binding.get('symbol_id'):
                        slots[str(index_binding['symbol_id'])] = index
                    try:
                        self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif opcode == 'control.for_each_map':
                result = None
                mapping = self._value(arguments.get('source'), slots)
                if not isinstance(mapping, dict):
                    raise RuntimeFailure('字典遍历的值必须是字典')
                items = list(mapping.items()) if arguments.get('snapshot') else mapping.items()
                bindings = arguments.get('bindings') or {}
                key_slot = str((bindings.get('key') or {}).get('symbol_id') or '')
                value_slot = str((bindings.get('value') or {}).get('symbol_id') or '')
                index_slot = str((bindings.get('index') or {}).get('symbol_id') or '')
                if not key_slot or not value_slot:
                    raise RuntimeFailure('字典遍历缺少键或值绑定')
                for index, (key, item) in enumerate(items):
                    if index >= 1_000_000:
                        raise RuntimeFailure('字典遍历超过 1000000 项，已启动安全保护')
                    if session.cancel_requested:
                        session.status = 'cancelled'
                        return
                    slots[key_slot], slots[value_slot] = key, item
                    if index_slot:
                        slots[index_slot] = index
                    try:
                        self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                    except _ContinueSignal:
                        continue
                    except _BreakSignal:
                        break
            elif opcode == 'control.break':
                raise _BreakSignal
            elif opcode == 'control.continue':
                raise _ContinueSignal
            elif opcode == 'control.fail':
                raise RuntimeFailure(
                    str(self._value(arguments.get('message'), slots)),
                    error_id=str(arguments.get('error_id') or 'project.explicit_failure'),
                    transient=False,
                    details=self._value(arguments.get('details'), slots),
                )
            elif opcode == 'control.try':
                result = None
                retry = arguments.get('retry_policy') or None
                max_retries = int(self._value(retry.get('max_retries'), slots)) if retry else 0
                interval = float(self._value(retry.get('interval'), slots)) if retry else 0.0
                attempts = 0
                try:
                    while True:
                        try:
                            self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                            break
                        except (_ReturnSignal, _BreakSignal, _ContinueSignal):
                            raise
                        except Exception as exc:
                            if attempts >= max_retries or (retry and retry.get('transient_only') and not getattr(exc, 'transient', False)):
                                raise
                            attempts += 1
                            self._event(session, 'warning', 'runtime', f'执行失败，准备第 {attempts} 次重试：{exc}', instruction_id)
                            deadline = time.monotonic() + max(0.0, interval) / 1000
                            while time.monotonic() < deadline:
                                self._checkpoint(
                                    session, instruction, slots, functions,
                                    depth, driver, allow_debug_break=False,
                                )
                                if session.cancel_requested:
                                    session.status = 'cancelled'
                                    return
                                time.sleep(min(0.02, deadline - time.monotonic()))
                except (_ReturnSignal, _BreakSignal, _ContinueSignal):
                    raise
                except Exception as exc:
                    error_id = str(getattr(exc, 'error_id', 'runtime.error'))
                    catcher = next((
                        item for item in (arguments.get('catches') or [])
                        if not item.get('error_ids') or error_id in item.get('error_ids', [])
                    ), None)
                    if catcher is None:
                        raise
                    target = str(catcher.get('error_slot') or '')
                    if target:
                        slots[target] = {
                            'error_id': error_id,
                            'message': str(exc),
                            'details': self._safe_diagnostic_value(getattr(exc, 'details', None)),
                        }
                    self._execute_block(session, catcher.get('body') or [], slots, functions, depth, driver)
                finally:
                    self._execute_block(session, arguments.get('finally') or [], slots, functions, depth, driver)
            elif opcode == 'control.retry':
                result = None
                count = self._value(arguments.get('count'), slots)
                if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                    raise RuntimeFailure('重试次数必须是正整数')
                last_error: Exception | None = None
                for attempt in range(1, count + 1):
                    try:
                        self._execute_block(session, arguments.get('body') or [], slots, functions, depth, driver)
                        last_error = None
                        break
                    except (_ReturnSignal, _BreakSignal, _ContinueSignal):
                        raise
                    except Exception as exc:
                        last_error = exc
                        if attempt < count:
                            self._event(
                                session, 'warning', 'runtime',
                                f'第 {attempt} 次执行失败，准备重试：{exc}', instruction_id,
                            )
                if last_error is not None:
                    raise last_error
            elif opcode == 'control.return':
                raw_value = arguments.get('value')
                raise _ReturnSignal(self._value(raw_value, slots) if raw_value is not None else None)
            elif opcode == 'control.target_scope':
                target = self._value(arguments.get('target'), slots)
                target_id = str(target.get('target_id') or '') if isinstance(target, dict) else ''
                if not target_id:
                    raise RuntimeFailure(
                        '目标作用域缺少稳定 target_id',
                        error_id='target.reference_invalid',
                    )
                if not isinstance(driver, _TargetScopeManager):
                    raise RuntimeFailure(
                        '当前运行宿主没有目标作用域调度器',
                        error_id='target.scope_host_missing',
                    )
                with driver.enter(target_id, instruction_id):
                    self._execute_block(
                        session, arguments.get('body') or [], slots,
                        functions, depth, driver,
                    )
                result = None
            elif opcode == 'control.listen':
                self._register_listener(
                    session, instruction, arguments, slots, functions,
                )
                result = None
            elif str(opcode).startswith('standard.'):
                from .standard_functions_v6 import StandardRuntimeV6

                driver_platform = str(getattr(driver, 'platform', '') or '')
                instruction_platforms = tuple(instruction.get('platforms') or ())
                if (
                    driver_platform and instruction_platforms
                    and driver_platform not in instruction_platforms
                ):
                    raise RuntimeFailure(
                        f'指令 {opcode} 不支持当前目标平台：{driver_platform}',
                        error_id='target.platform_unsupported',
                    )
                evaluated = {
                    name: self._value(value, slots) for name, value in arguments.items()
                }
                result = StandardRuntimeV6().execute(
                    str(opcode),
                    str(instruction.get('function_id') or ''),
                    evaluated,
                    driver,
                    lambda: session.cancel_requested,
                    lambda message, _instruction_id=instruction_id: self._event(
                        session, 'info', 'standard', message, _instruction_id,
                    ),
                    safe_checkpoint=lambda _instruction=instruction: self._checkpoint(
                        session, _instruction, slots, functions, depth, driver,
                        allow_debug_break=False,
                    ),
                )
            elif str(opcode).startswith(('file.', 'directory.')):
                from .file_runtime_v6 import FileRuntimeV6

                evaluated = {
                    name: self._value(value, slots) for name, value in arguments.items()
                }
                result = FileRuntimeV6().execute(
                    str(opcode),
                    str(instruction.get('function_id') or ''),
                    evaluated,
                    lambda: session.cancel_requested,
                    operation_context={
                        'instruction_id': instruction_id,
                        'confirmation': copy.deepcopy(
                            session.dangerous_confirmations.get(instruction_id) or {}
                        ),
                        'protected_roots': [
                            item for item in (
                                session.project_path,
                                session.runtime_data_directory,
                            ) if item
                        ],
                    },
                )
            elif str(opcode).startswith('message.'):
                from .message_runtime_v6 import MessageRuntimeV6

                if not session.message_context:
                    raise RuntimeFailure(
                        '消息函数需要稳定运行实例身份',
                        error_id='message.instance_unknown',
                    )
                if session._message_runtime is None:
                    session._message_runtime = MessageRuntimeV6(
                        session.message_context.get('database_path') or None,
                        lan_root=session.message_context.get('lan_root') or None,
                    )
                evaluated = {
                    name: self._value(value, slots) for name, value in arguments.items()
                }
                result = session._message_runtime.execute(
                    str(opcode),
                    str(instruction.get('function_id') or ''),
                    evaluated,
                    session.message_context,
                    lambda: session.cancel_requested,
                    lambda message, _instruction_id=instruction_id: self._event(
                        session,
                        'info',
                        'message',
                        message,
                        _instruction_id,
                    ),
                    safe_checkpoint=lambda _instruction=instruction: self._checkpoint(
                        session, _instruction, slots, functions, depth, driver,
                        allow_debug_break=False,
                    ),
                )
            elif str(opcode).startswith('network.'):
                from .network_runtime_v6 import NetworkRuntimeV6

                if session._network_runtime is None:
                    session._network_runtime = NetworkRuntimeV6()
                evaluated = {
                    name: self._value(value, slots) for name, value in arguments.items()
                }
                result = session._network_runtime.execute(
                    str(opcode),
                    str(instruction.get('function_id') or ''),
                    evaluated,
                    instruction.get('network_authorization') or {},
                    lambda: session.cancel_requested,
                    lambda payload, _instruction_id=instruction_id: self._event(
                        session,
                        'info' if not payload.get('error_id') else 'warning',
                        'network',
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        _instruction_id,
                    ),
                )
            elif str(opcode) in _PLATFORM_RUNTIME_OPCODES:
                from .platform_runtime_v6 import PlatformRuntimeV6

                if session._platform_runtime is None:
                    session._platform_runtime = PlatformRuntimeV6()
                evaluated = {
                    name: self._value(value, slots) for name, value in arguments.items()
                }
                result = session._platform_runtime.execute(
                    str(opcode),
                    str(instruction.get('function_id') or ''),
                    evaluated,
                    driver,
                    lambda: session.cancel_requested,
                    lambda message, _instruction_id=instruction_id, _opcode=str(opcode): self._event(
                        session,
                        'info',
                        'application' if _opcode.startswith('host.app.') else 'target',
                        message,
                        _instruction_id,
                    ),
                    safe_checkpoint=lambda _instruction=instruction: self._checkpoint(
                        session, _instruction, slots, functions, depth, driver,
                        allow_debug_break=False,
                    ),
                )
            elif driver is not None and hasattr(driver, 'supports') and driver.supports(opcode):
                driver_platform = str(getattr(driver, 'platform', '') or '')
                instruction_platforms = tuple(instruction.get('platforms') or ())
                if (
                    driver_platform and instruction_platforms
                    and driver_platform not in instruction_platforms
                ):
                    raise RuntimeFailure(
                        f'指令 {opcode} 不支持当前目标平台：{driver_platform}',
                        error_id='target.platform_unsupported',
                    )
                if str(opcode).startswith(('frame.', 'color.', 'vision.', 'text.', 'input.', 'control.')) and hasattr(driver, 'before_screen_operation'):
                    driver.before_screen_operation(
                        lambda: session.cancel_requested,
                        lambda value: self._value(value, slots),
                        lambda action: self._execute_block(session, [action], slots, functions, depth, driver),
                        lambda message, _instruction_id=instruction_id: self._event(session, 'info', 'popup', message, _instruction_id),
                    )
                evaluated = {name: self._value(value, slots) for name, value in arguments.items()}
                result = driver.execute(opcode, evaluated, lambda: session.cancel_requested)
                message = result.get('message') if isinstance(result, dict) else ''
                if not message and hasattr(driver, 'consume_message'):
                    message = driver.consume_message()
                if message:
                    self._event(session, 'info', 'target', str(message), instruction_id)
            else:
                capabilities = '、'.join(instruction.get('capabilities') or []) or '对应目标驱动'
                target_opcode = str(opcode).startswith(('target.', 'frame.', 'vision.', 'input.', 'text.'))
                target_missing = driver is None or (
                    isinstance(driver, _TargetScopeManager) and driver.current is None
                )
                raise RuntimeFailure(
                    f'指令 {opcode} 尚未绑定运行驱动（需要：{capabilities}）',
                    error_id=(
                        'target.missing'
                        if target_opcode and target_missing
                        else 'target.capability_unsupported'
                    ),
                )
            result_slot = instruction.get('result_slot')
            if result_slot:
                slots[str(result_slot)] = result
            session.variables = {
                key: value for key, value in slots.items() if not key.startswith('__')
            }
        if session.cancel_requested:
            session.status = 'cancelled'
            return
        boundary_instruction = (
            instructions[-1]
            if instructions else {
                'instruction_id': session.current_instruction_id,
                'source': session.current_source,
            }
        )
        self._checkpoint(
            session, boundary_instruction, slots, functions, depth, driver,
            allow_debug_break=False,
        )

    def snapshot(self, execution_id: str, after_sequence: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._prune_sessions()
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            session.last_access_monotonic = time.monotonic()
            return session.snapshot(after_sequence)

    def latest_snapshot(self, after_sequence: int | None = None) -> dict[str, Any] | None:
        """Return the newest retained run without inventing a second run registry.

        The Windows Player console uses this read-only projection to show the
        state of one isolated Player worker.  Session ownership and all
        mutations remain in the ordinary runtime endpoints.
        """

        with self._lock:
            self._prune_sessions()
            if not self._sessions:
                return None
            session = max(
                self._sessions.values(),
                key=lambda item: (str(item.started_at or ''), item.execution_id),
            )
            session.last_access_monotonic = time.monotonic()
            return session.snapshot(after_sequence)

    def active_snapshots(self, project_path: str) -> list[dict[str, Any]]:
        """Return active runs owned by one project, newest first.

        Browser refreshes replace the IDE renderer but must not replace or
        abandon the runtime session.  The workspace-scoped API uses this
        projection to reattach the new renderer without creating a second run.
        """

        expected_path = os.path.normcase(os.path.realpath(os.path.abspath(project_path)))
        with self._lock:
            self._prune_sessions()
            sessions = [
                session
                for session in self._sessions.values()
                if session.status in {'queued', 'running', 'paused'}
                and session.project_path
                and os.path.normcase(
                    os.path.realpath(os.path.abspath(session.project_path))
                ) == expected_path
            ]
            sessions.sort(
                key=lambda item: (str(item.started_at or ''), item.execution_id),
                reverse=True,
            )
            now = time.monotonic()
            for session in sessions:
                session.last_access_monotonic = now
            return [session.snapshot() for session in sessions]

    def wait_snapshot(self, execution_id: str, after_sequence: int, timeout: float = 15.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, min(float(timeout), 30.0))
        with self._events_changed:
            while True:
                session = self._sessions.get(execution_id)
                if session is None:
                    raise RuntimeFailure('运行会话不存在')
                if (
                    session.next_event_sequence > after_sequence
                    or (session.status in {'completed', 'failed', 'cancelled'} and bool(session.finished_at))
                ):
                    session.last_access_monotonic = time.monotonic()
                    return session.snapshot(after_sequence)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return session.snapshot(after_sequence)
                self._events_changed.wait(remaining)

    def cancel(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            session.cancel_requested = True
            if session._resume_gate is not None:
                session._resume_gate.set()
            if session._worker_proxy is not None:
                session.cancel_deadline = time.monotonic() + 3.0
                session._worker_proxy.send('cancel')
            return session.snapshot()

    def pause(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            if session.status not in {'queued', 'running'}:
                raise RuntimeFailure('当前运行状态不能暂停')
            session.pause_requested = True
            if session._worker_proxy is not None:
                session._worker_proxy.send('pause')
            return session.snapshot()

    def resume(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            if session.status != 'paused':
                raise RuntimeFailure('当前运行状态未暂停')
            if session._worker_proxy is not None:
                session._worker_proxy.send('resume')
            else:
                if session._resume_gate is None:
                    raise RuntimeFailure('运行会话的暂停状态已结束')
                session._resume_gate.set()
            return session.snapshot()

    def step(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            if session.status != 'paused':
                raise RuntimeFailure('单步执行前必须先暂停')
            if session._worker_proxy is not None:
                session._worker_proxy.send('step')
            else:
                if session._resume_gate is None:
                    raise RuntimeFailure('运行会话的暂停状态已结束')
                session.pause_after_instruction = True
                session._resume_gate.set()
            return session.snapshot()

    def shutdown(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            proxy = session._worker_proxy
            if proxy is not None and proxy.is_alive():
                proxy.send('cancel')
                proxy.join(timeout=1.5)
                if proxy.is_alive():
                    proxy.terminate_tree()
                    proxy.join(timeout=1.0)
            self._close_event_log(session)

    def diagnostic_path(self, execution_id: str) -> str:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            if not session.diagnostic_bundle or not os.path.isfile(session.diagnostic_bundle):
                raise RuntimeFailure('当前运行没有可用诊断包')
            return session.diagnostic_bundle

    def failure_frame_path(self, execution_id: str) -> str:
        with self._lock:
            session = self._sessions.get(execution_id)
            if session is None:
                raise RuntimeFailure('运行会话不存在')
            if not session.failure_frame or not os.path.isfile(session.failure_frame):
                raise RuntimeFailure('当前运行没有可用失败截图')
            return session.failure_frame


vnext_runtime = VNextRuntime(use_worker_process=True)
