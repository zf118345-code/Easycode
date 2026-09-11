"""Spawn-safe Player execution worker and lightweight parent proxy."""

from __future__ import annotations

import multiprocessing
import os
import queue
import sys
import tempfile
import threading
import time
from typing import Any

from core.security import atomic_write_json


def _safe_put(events, payload: dict, *, final: bool = False):
    try:
        events.put(payload, timeout=1.0 if final else 0.02)
    except Exception:
        pass


def _redact(value, secret_values):
    if not secret_values:
        return value
    from core.services.player_secret_service import PlayerSecretService

    return PlayerSecretService.redact(value, secret_values)


def _make_console_non_fatal():
    """Keep inherited Windows console encoding errors from breaking a worker."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors='replace')
        except (OSError, ValueError, TypeError):
            # Detached/embedded Player processes may not own a valid console.
            pass


def execution_worker_main(payload: dict, events, start_event, stop_event):
    """Child entry point. It must remain module-level for Windows spawn."""
    _make_console_non_fatal()
    executor = None
    stop_thread = None
    watcher_shutdown = threading.Event()
    try:
        from core.executor import GraphExecutor
        from core.project_loader import load_project, project_from_dict
        from core.services.platform_runtime_service import platform_runtime_service
        if payload.get('_ocr_process_semaphore') is not None:
            from core.vision import ocr_engine

            ocr_engine._OCR_PROCESS_SEMAPHORE = payload['_ocr_process_semaphore']

        project_path = str(payload['project_path'])
        blueprint = payload.get('blueprint') or {}
        if payload.get('persist_blueprint'):
            project = load_project(project_path)
        else:
            project = project_from_dict(blueprint, 'player-runtime')
        executor = GraphExecutor(
            project,
            project_dir=project_path,
            text_log_enabled=True,
            image_log_enabled=True,
            initial_context=payload.get('context') or {},
        )
        if blueprint.get('_memory_templates'):
            executor._memory_templates = blueprint['_memory_templates']
        runtime_dir = payload.get('runtime_dir')
        if payload.get('persist_blueprint'):
            executor._platform_store = platform_runtime_service.register_project(project_path)
        else:
            player_root = os.path.dirname(runtime_dir) if runtime_dir else os.path.dirname(project_path)
            executor._platform_store = platform_runtime_service.register_player(player_root)

        original_log = executor.log
        redact_values = payload.get('redact_values') or []

        def sanitize(value):
            return _redact(value, redact_values)

        def worker_log(message, *args, **kwargs):
            before = len(executor.logs)
            result = original_log(message, *args, **kwargs)
            for item in executor.logs[before:]:
                _safe_put(events, {'type': 'log', 'log': sanitize(dict(item))})
            return result

        executor.log = worker_log

        checkpoint_path = payload.get('checkpoint_path')
        if checkpoint_path:
            os.makedirs(os.path.dirname(os.path.abspath(checkpoint_path)), exist_ok=True)

            def save_checkpoint(task_id, node_id, variables):
                if getattr(executor, '_active_frame', None) and executor._active_frame.get('call_depth', 0) > 0:
                    return
                value = {
                    'execution_id': payload['execution_id'],
                    'instance_id': payload.get('instance_id'),
                    'task_id': task_id,
                    'node_id': node_id,
                    'variables': variables,
                    'updated_at': time.time(),
                }
                checkpoint_storage_root = payload.get('checkpoint_storage_root')
                if checkpoint_storage_root:
                    from core.services.player_secret_service import PlayerSecretService

                    value = PlayerSecretService.protect_document(value, checkpoint_storage_root)
                atomic_write_json(
                    checkpoint_path,
                    value,
                    clean_transient=False,
                    default=str,
                )

            executor.checkpoint_callback = save_checkpoint

        uses_screen = any(
            executor._node_requires_popup_check(node) or node.node_type in {'set_window', 'script_call'}
            for task in executor.tasks.values()
            for node in task.nodes
        )
        target_key = None
        if uses_screen:
            if executor.is_emulator:
                target_key = f'adb:{executor.device_id}'
            elif executor.window_hwnd:
                target_key = f'hwnd:{int(executor.window_hwnd)}'
            else:
                target_key = 'desktop'
        _safe_put(events, {
            'type': 'ready', 'target_key': target_key, 'pid': os.getpid(),
            'capture': getattr(executor, '_last_capture_info', None),
        }, final=True)
        if not start_event.wait(15.0):
            raise RuntimeError('主进程未在 15 秒内授予目标资源租约')

        def watch_stop():
            # Do not block forever inside multiprocessing.Event.wait().  On
            # Windows a worker exiting while that daemon thread owns the
            # shared condition can make the parent's Event.set() deadlock.
            while not watcher_shutdown.wait(0.05):
                if stop_event.is_set():
                    executor.stop()
                    return

        stop_thread = threading.Thread(target=watch_stop, name='easycode-worker-stop', daemon=True)
        stop_thread.start()
        executor.run(str(payload['task_id']), str(payload['start_node_id']))
        latest_frame_path = None
        latest_frame = getattr(executor, '_step_screen', None)
        if latest_frame is not None and payload.get('runtime_dir'):
            try:
                os.makedirs(payload['runtime_dir'], exist_ok=True)
                latest_frame_path = os.path.join(
                    payload['runtime_dir'], f'last-frame-{payload.get("execution_id", "worker")}.png',
                )
                latest_frame.save(latest_frame_path, format='PNG', compress_level=3)
            except Exception:
                latest_frame_path = None
        _safe_put(events, {
            'type': 'final',
            'status': 'stopped' if executor.is_stopped else 'success',
            'message': sanitize('用户主动停止' if executor.is_stopped else '执行完成'),
            'latest_frame': latest_frame_path,
            'runtime_metrics': {
                'capture': getattr(executor, '_last_capture_info', None),
                'input_capabilities': getattr(executor, '_input_capability_profile', None),
                'frame_stream': (
                    executor._visual_frame_stream.metrics()
                    if getattr(executor, '_visual_frame_stream', None) is not None
                    and hasattr(executor._visual_frame_stream, 'metrics') else None
                ),
            },
        }, final=True)
    except Exception as exc:
        screenshot_path = None
        if executor is not None:
            try:
                from core.services.runtime_target import capture_workspace

                target_dir = payload.get('runtime_dir') or os.path.join(tempfile.gettempdir(), 'EasycodePlayer', 'diagnostics')
                os.makedirs(target_dir, exist_ok=True)
                screenshot_path = os.path.join(target_dir, f'failure-{payload.get("execution_id", "worker")}.png')
                capture_workspace(executor).save(screenshot_path)
            except Exception:
                screenshot_path = None
        _safe_put(events, {
            'type': 'final', 'status': 'error',
            'message': _redact(str(exc), payload.get('redact_values') or []),
            'failure_screenshot': screenshot_path,
        }, final=True)
    finally:
        watcher_shutdown.set()
        if stop_thread is not None and stop_thread.is_alive():
            stop_thread.join(timeout=0.25)


class ExecutionWorkerProxy:
    def __init__(self, process, events, start_event, stop_event):
        self.process = process
        self.events = events
        self.start_event = start_event
        self.stop_event = stop_event
        self.started_at = time.monotonic()
        self.target_key = None
        self.last_metrics: dict[str, Any] = {}

    def stop(self):
        if self.process.is_alive():
            self.stop_event.set()

    @property
    def is_stopped(self):
        return self.stop_event.is_set()

    def metrics(self) -> dict[str, Any]:
        result = {
            'pid': self.process.pid,
            'alive': self.process.is_alive(),
            'exit_code': self.process.exitcode,
            'uptime_ms': round((time.monotonic() - self.started_at) * 1000, 2),
            **self.last_metrics,
        }
        try:
            import psutil

            process = psutil.Process(self.process.pid)
            memory = process.memory_info()
            result.update({'cpu_percent': process.cpu_percent(None), 'rss_bytes': memory.rss})
        except Exception:
            pass
        return result


_SPAWN_CONTEXT = multiprocessing.get_context('spawn')
_OCR_PROCESS_SEMAPHORE = _SPAWN_CONTEXT.BoundedSemaphore(
    max(1, int(os.environ.get('EASYCODE_OCR_WORKERS', '2') or 2)),
)


def spawn_execution_worker(payload: dict) -> ExecutionWorkerProxy:
    context = _SPAWN_CONTEXT
    payload = {**payload, '_ocr_process_semaphore': _OCR_PROCESS_SEMAPHORE}
    events = context.Queue(maxsize=2048)
    start_event = context.Event()
    stop_event = context.Event()
    process = context.Process(
        target=execution_worker_main,
        args=(payload, events, start_event, stop_event),
        name=f'easycode-worker-{str(payload.get("instance_id") or payload["execution_id"])[-18:]}',
        daemon=False,
    )
    process.start()
    return ExecutionWorkerProxy(process, events, start_event, stop_event)


def next_worker_event(proxy: ExecutionWorkerProxy, timeout: float = 0.25):
    try:
        return proxy.events.get(timeout=timeout)
    except queue.Empty:
        return None
