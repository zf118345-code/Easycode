"""Spawn-safe vNext execution worker and its parent-side IPC proxy."""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import queue
import sys
import threading
import time
from dataclasses import asdict
from typing import Any


def _safe_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if not callable(reconfigure):
            continue
        with contextlib.suppress(OSError, TypeError, ValueError):
            reconfigure(encoding='utf-8', errors='backslashreplace')


def _put(events, payload: dict[str, Any], *, final: bool = False) -> None:
    try:
        events.put(payload, timeout=2.0 if final else 1.0)
    except Exception:
        if final:
            raise


def vnext_execution_worker_main(payload: dict[str, Any], events, commands) -> None:
    """Run one ECIR session. Kept module-level for Windows spawn/PyInstaller."""

    _safe_console()
    runtime = None
    execution_id = str(payload['execution_id'])
    try:
        from .runtime import VNextRuntime
        from .target_runtime import create_target_driver

        def emit(event) -> None:
            _put(events, {'type': 'event', 'event': asdict(event)})

        runtime = VNextRuntime(
            event_buffer_size=1000,
            max_sessions=1,
            session_ttl_seconds=24 * 60 * 60,
            persist_event_log=True,
            event_sink=emit,
        )
        ecir = dict(payload.get('ecir') or {})
        project_path = str(ecir.get('project_path') or payload.get('project_path') or '')
        target = payload.get('target')
        driver = create_target_driver(project_path, target) if target else None
        started = runtime.start(
            ecir, driver, payload.get('debug') or {},
            execution_id=execution_id,
            message_context=dict(payload.get('message_context') or {}),
        )
        session = runtime._sessions[execution_id]
        _put(events, {
            'type': 'ready', 'pid': os.getpid(),
            'event_log_path': session.event_log_path,
            'snapshot': started,
        }, final=True)
        last_state = 0.0
        while True:
            while True:
                try:
                    command = commands.get_nowait()
                except queue.Empty:
                    break
                action = str((command or {}).get('action') or '')
                if action == 'cancel':
                    runtime.cancel(execution_id)
                elif action == 'pause':
                    runtime.pause(execution_id)
                elif action == 'resume':
                    runtime.resume(execution_id)
                elif action == 'step':
                    runtime.step(execution_id)
            snapshot = runtime.snapshot(execution_id, after_sequence=session.next_event_sequence)
            now = time.monotonic()
            terminal = snapshot['status'] in {'completed', 'failed', 'cancelled'} and bool(snapshot.get('finished_at'))
            if now - last_state >= 0.25 or terminal:
                _put(events, {'type': 'state', 'snapshot': snapshot})
                last_state = now
            if terminal:
                _put(events, {
                    'type': 'final', 'snapshot': snapshot,
                    'diagnostic_bundle': session.diagnostic_bundle,
                    'failure_frame': session.failure_frame,
                    'event_log_path': session.event_log_path,
                }, final=True)
                return
            time.sleep(0.02)
    except BaseException as exc:
        _put(events, {
            'type': 'fatal', 'error': str(exc),
            'execution_id': execution_id,
        }, final=True)
    finally:
        if runtime is not None:
            runtime.shutdown()


class VNextWorkerProxy:
    def __init__(self, process, events, commands) -> None:
        self.process = process
        self.events = events
        self.commands = commands
        self.started_at = time.monotonic()
        self.closed = False
        self._lifecycle_lock = threading.RLock()

    def is_alive(self) -> bool:
        with self._lifecycle_lock:
            if self.closed:
                return False
            with contextlib.suppress(Exception):
                return bool(self.process.is_alive())
        return False

    def join(self, timeout: float | None = None) -> None:
        """Wait for the worker without racing the monitor's handle cleanup."""

        with self._lifecycle_lock:
            if self.closed:
                return
            with contextlib.suppress(OSError, ValueError):
                self.process.join(timeout=timeout)

    def send(self, action: str) -> None:
        if not self.is_alive():
            return
        with contextlib.suppress(Exception):
            self.commands.put({'action': action}, timeout=0.25)

    def receive(self, timeout: float = 0.25) -> dict[str, Any] | None:
        with self._lifecycle_lock:
            if self.closed or self.events is None:
                return None
            events = self.events
        try:
            value = events.get(timeout=timeout)
            return value if isinstance(value, dict) else None
        except (OSError, ValueError, EOFError, queue.Empty):
            return None

    def terminate_tree(self) -> None:
        with self._lifecycle_lock:
            if self.closed:
                return
            with contextlib.suppress(Exception):
                if not self.process.is_alive():
                    return
                if os.name == 'nt' and self.process.pid:
                    import subprocess

                    try:
                        subprocess.run(
                            ['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=5, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                        )
                    except Exception:
                        self.process.terminate()
                else:
                    self.process.terminate()

    def close(self) -> None:
        with self._lifecycle_lock:
            if self.closed:
                return
            channels = (self.events, self.commands)
            # Mark the proxy closed before releasing native handles so another
            # shutdown caller cannot start a join against a half-closed Process.
            self.closed = True
            self.events = None
            self.commands = None
            for channel in channels:
                try:
                    channel.close()
                except Exception:
                    pass
                try:
                    # Release the Queue feeder thread and its pipe/semaphore handles.
                    # This runs only after the worker has exited, so draining cannot
                    # deadlock behind a live producer.
                    channel.join_thread()
                except Exception:
                    with contextlib.suppress(Exception):
                        channel.cancel_join_thread()
                for endpoint_name in ('_reader', '_writer'):
                    endpoint = getattr(channel, endpoint_name, None)
                    with contextlib.suppress(Exception):
                        endpoint.close()
            # multiprocessing.Process keeps its native process/sentinel handles
            # until close() is called even after join(). A long-lived Player starts
            # many one-shot workers, so relying on Python GC leaks observable Windows
            # handles between runs.
            with contextlib.suppress(Exception):
                self.process.close()


_CONTEXT = multiprocessing.get_context('spawn')


def spawn_vnext_worker(payload: dict[str, Any]) -> VNextWorkerProxy:
    events = _CONTEXT.Queue(maxsize=4096)
    commands = _CONTEXT.Queue(maxsize=64)
    process = _CONTEXT.Process(
        target=vnext_execution_worker_main,
        args=(payload, events, commands),
        name=f'easycode-vnext-{str(payload["execution_id"])[-12:]}',
        daemon=False,
    )
    process.start()
    return VNextWorkerProxy(process, events, commands)
