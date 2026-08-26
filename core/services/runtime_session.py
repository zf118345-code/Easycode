"""Low-latency runtime primitives shared by visual nodes.

The graph executor describes *what* to do.  This module owns the hot path used
while a node is waiting on pixels: keep only the newest frame, overlap capture
with matching, and reuse an Android input channel instead of spawning a host
process for every tap.

The current Android frame producer still uses the configured runtime capture
backend.  It is deliberately exposed as a capability (``standard`` today) so
that a scrcpy streaming producer can replace it without changing node
semantics.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class FramePacket:
    """One captured frame and its position inside the workspace."""

    image: Any
    region: tuple[int, int, int, int]
    sequence: int
    captured_at_ns: int
    capture_duration_ms: float
    provider: str = 'standard_capture'


class LatestFrameStream:
    """Capture on a worker thread and expose a single-slot latest-frame buffer.

    Consumers never work through stale queues: if matching is slower than
    capture, intermediate frames are overwritten.  That property is essential
    for stop conditions where acting on an old frame may click the next page.
    """

    def __init__(
        self,
        capture: Callable[[], tuple[Any, tuple[int, int, int, int]]],
        *,
        min_interval_ms: int = 0,
        name: str = 'easycode-frame-stream',
    ):
        self._capture = capture
        self._min_interval_s = max(0, int(min_interval_ms or 0)) / 1000.0
        self._name = name
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest: FramePacket | None = None
        self._sequence = 0
        self._error: Exception | None = None
        self.provider = 'standard_capture'
        self._captured = 0
        self._consumed = 0
        self._overwritten = 0
        self._capture_total_ms = 0.0
        self._last_consumer_ns = time.monotonic_ns()
        self._last_delivery_sequence = 0
        self._effective_interval_ms = max(0, int(min_interval_ms or 0))

    def start(self) -> 'LatestFrameStream':
        if self._thread and self._thread.is_alive():
            return self
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        while not self._stop_event.is_set():
            started_ns = time.monotonic_ns()
            try:
                captured = self._capture()
                if isinstance(captured, tuple) and len(captured) >= 3:
                    image, region, metadata = captured[0], captured[1], captured[2]
                else:
                    image, region = captured
                    metadata = {}
                completed_ns = time.monotonic_ns()
                with self._condition:
                    self._sequence += 1
                    duration_ms = (completed_ns - started_ns) / 1_000_000.0
                    provider = str((metadata or {}).get('provider') or self.provider)
                    self.provider = provider
                    self._captured += 1
                    self._capture_total_ms += duration_ms
                    self._latest = FramePacket(
                        image=image,
                        region=tuple(int(value) for value in region),
                        sequence=self._sequence,
                        captured_at_ns=completed_ns,
                        capture_duration_ms=duration_ms,
                        provider=provider,
                    )
                    self._error = None
                    self._condition.notify_all()
            except Exception as exc:  # capture failures must wake the node immediately
                with self._condition:
                    self._error = exc
                    self._condition.notify_all()
                return

            elapsed_s = (time.monotonic_ns() - started_ns) / 1_000_000_000.0
            idle_s = (time.monotonic_ns() - self._last_consumer_ns) / 1_000_000_000.0
            # When matching/logging is not consuming frames, avoid a producer
            # busy-loop. Active high-speed consumers still get the configured
            # interval (0 means one cooperative 1ms yield).
            adaptive_interval_s = max(self._min_interval_s, 0.05 if idle_s >= 0.25 else 0.001)
            self._effective_interval_ms = int(round(adaptive_interval_s * 1000))
            remaining_s = adaptive_interval_s - elapsed_s
            if remaining_s > 0:
                self._stop_event.wait(remaining_s)

    def next(self, after_sequence: int = 0, timeout_s: float | None = None) -> FramePacket:
        """Wait for a frame newer than ``after_sequence``.

        Raises ``TimeoutError`` on deadline and re-raises capture errors.  A
        caller can therefore distinguish a clean visual timeout from a broken
        capture provider.
        """

        self.start()
        deadline = None if timeout_s is None else time.monotonic() + max(0.0, timeout_s)
        with self._condition:
            while True:
                if self._latest is not None and self._latest.sequence > after_sequence:
                    self._consumed += 1
                    gap = max(0, self._latest.sequence - max(after_sequence, self._last_delivery_sequence) - 1)
                    self._overwritten += gap
                    self._last_delivery_sequence = self._latest.sequence
                    self._last_consumer_ns = time.monotonic_ns()
                    return self._latest
                if self._error is not None:
                    raise RuntimeError(f'画面采集失败: {self._error}') from self._error
                if self._stop_event.is_set():
                    raise RuntimeError('画面采集会话已停止')
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError('等待新画面超时')
                self._condition.wait(remaining)

    def stop(self, join_timeout_s: float = 0.25):
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(max(0.0, join_timeout_s))

    def metrics(self) -> dict[str, Any]:
        with self._condition:
            latest = self._latest
            return {
                'provider': self.provider,
                'captured_frames': self._captured,
                'consumed_frames': self._consumed,
                'overwritten_frames': self._overwritten,
                'average_capture_ms': round(self._capture_total_ms / self._captured, 3) if self._captured else 0.0,
                'effective_interval_ms': self._effective_interval_ms,
                'latest_frame_age_ms': round((time.monotonic_ns() - latest.captured_at_ns) / 1_000_000, 3) if latest else None,
                'error': str(self._error) if self._error else '',
            }

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()


class RecoveringAndroidFrameView:
    """Bounded scrcpy reconnect wrapper; one device failure stays in its Worker."""

    provider = 'scrcpy_stream'

    def __init__(self, context, workspace_size, capture_region, *, max_reconnects: int = 2):
        self.context = context
        self.workspace_size = workspace_size
        self.capture_region = capture_region
        self.max_reconnects = max(0, int(max_reconnects))
        self.reconnect_count = 0
        self._sequence = 0
        self._view = None

    def _open(self):
        from core.services.android_stream import AndroidFrameView, get_android_video_session

        session = get_android_video_session(self.context, self.workspace_size)
        session.start()
        self._view = AndroidFrameView(session, workspace_size=self.workspace_size, capture_region=self.capture_region)

    def start(self):
        if self._view is None:
            self._open()
        return self

    def next(self, _after_sequence: int = 0, timeout_s: float | None = None):
        deadline = None if timeout_s is None else time.monotonic() + max(0.0, timeout_s)
        while True:
            try:
                self.start()
                remaining = None if deadline is None else max(0.001, deadline - time.monotonic())
                packet = self._view.next(0, remaining)
                self._sequence += 1
                return replace(packet, sequence=self._sequence, provider=self.provider)
            except Exception as exc:
                if self.reconnect_count >= self.max_reconnects:
                    raise RuntimeError(f'Android高速采帧熔断（已重连 {self.reconnect_count} 次）: {exc}') from exc
                self.reconnect_count += 1
                failed = getattr(self.context, '_android_video_session', None)
                if failed is not None and hasattr(failed, 'close'):
                    failed.close()
                try:
                    delattr(self.context, '_android_video_session')
                except AttributeError:
                    pass
                self._view = None
                logger = getattr(self.context, 'log', None)
                if callable(logger):
                    logger(f'[Android采帧] 通道断开，第 {self.reconnect_count}/{self.max_reconnects} 次重连: {exc}', 'warning')
                delay = min(1.0, 0.1 * (2 ** (self.reconnect_count - 1)))
                if deadline is not None and time.monotonic() + delay >= deadline:
                    raise TimeoutError('Android采帧重连超过节点剩余超时') from exc
                time.sleep(delay)

    def stop(self):
        session = getattr(self.context, '_android_video_session', None)
        if session is not None and hasattr(session, 'close'):
            session.close()
        self._view = None

    def metrics(self):
        return {'provider': self.provider, 'reconnect_count': self.reconnect_count}

    def __enter__(self):
        return self.start()

    def __exit__(self, *_args):
        self.stop()


@dataclass
class _TemplateEntry:
    signature: tuple[int, int] | None
    value: Any


class TemplateCache:
    """Thread-safe bounded cache for decoded template matrices."""

    def __init__(self, max_entries: int = 256):
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.RLock()
        self._entries: OrderedDict[str, _TemplateEntry] = OrderedDict()

    @staticmethod
    def _signature(path: str) -> tuple[int, int] | None:
        try:
            stat = os.stat(path)
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            # The loader will produce the authoritative error.  Keeping None
            # also makes fake paths straightforward in isolated unit tests.
            return None

    def get(self, path: str, loader: Callable[[str], Any]) -> tuple[Any, bool]:
        normalized = str(Path(path).resolve(strict=False))
        signature = self._signature(normalized)
        with self._lock:
            entry = self._entries.get(normalized)
            if entry is not None and entry.signature == signature:
                self._entries.move_to_end(normalized)
                return entry.value, True

        value = loader(path)
        with self._lock:
            self._entries[normalized] = _TemplateEntry(signature=signature, value=value)
            self._entries.move_to_end(normalized)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return value, False

    def clear(self):
        with self._lock:
            self._entries.clear()


class PersistentAdbInputSession:
    """Warm ``adb shell`` transport used as the first low-latency Android input tier.

    It removes host-side adb process creation per tap.  Delivery is still
    explicitly reported as unverified; a future scrcpy control provider can
    implement the same ``tap`` contract with lower device-side overhead.
    """

    def __init__(self, device_id: str, adb_path: str = 'adb'):
        self.device_id = str(device_id or '').strip()
        self.adb_path = adb_path
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._condition = threading.Condition()
        self._ready = False
        self._sequence = 0
        self._acks: dict[int, int] = {}

    @staticmethod
    def _startup_info() -> dict:
        if os.name != 'nt':
            return {}
        return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}

    def start(self):
        if not self.device_id:
            raise RuntimeError('ADB设备序列号为空')
        if self._process is not None and self._process.poll() is None:
            return
        self._process = subprocess.Popen(
            [self.adb_path, '-s', self.device_id, 'shell'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding='utf-8',
            bufsize=1,
            **self._startup_info(),
        )
        if self._process.poll() is not None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError('ADB持久输入通道启动失败')
        self._ready = False
        self._reader = threading.Thread(target=self._read_output, name='easycode-adb-input', daemon=True)
        self._reader.start()
        self._process.stdin.write('echo __EASYCODE_READY__\n')
        self._process.stdin.flush()
        deadline = time.monotonic() + 1.5
        with self._condition:
            while not self._ready:
                if self._process.poll() is not None:
                    raise RuntimeError(f'ADB持久输入通道提前退出（代码 {self._process.returncode}）')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('ADB持久输入通道握手超时')
                self._condition.wait(remaining)

    def _read_output(self):
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                with self._condition:
                    if line == '__EASYCODE_READY__':
                        self._ready = True
                    elif line.startswith('__EASYCODE_ACK__'):
                        payload = line.removeprefix('__EASYCODE_ACK__')
                        sequence, _, code = payload.partition(':')
                        try:
                            self._acks[int(sequence)] = int(code)
                        except ValueError:
                            pass
                    self._condition.notify_all()
        finally:
            with self._condition:
                self._condition.notify_all()

    def tap(self, x: int, y: int) -> dict[str, Any]:
        return self._execute_input_command(
            f'input tap {int(x)} {int(y)}',
            action='点击',
            success_message=f'坐标({int(x)},{int(y)})',
        )

    def _execute_input_command(
        self,
        command: str,
        *,
        action: str,
        success_message: str,
        timeout_s: float = 2.0,
    ) -> dict[str, Any]:
        """在持久 adb shell 中执行一条经调用方安全组装的 input 命令。"""
        with self._lock:
            self.start()
            assert self._process is not None and self._process.stdin is not None
            self._sequence += 1
            sequence = self._sequence
            try:
                self._process.stdin.write(
                    f'{command}; echo __EASYCODE_ACK__{sequence}:$?\n'
                )
                self._process.stdin.flush()
            except Exception as exc:
                self.close()
                return {
                    'ok': False,
                    'method': 'adb_persistent',
                    'delivery': 'failed',
                    'message': f'ADB持久{action}失败: {exc}',
                }
            deadline = time.monotonic() + max(0.1, float(timeout_s or 2.0))
            with self._condition:
                while sequence not in self._acks:
                    if self._process.poll() is not None:
                        return {
                            'ok': False,
                            'method': 'adb_persistent',
                            'delivery': 'failed',
                            'message': f'ADB持久输入通道已退出（代码 {self._process.returncode}）',
                        }
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return {
                            'ok': False,
                            'method': 'adb_persistent',
                            'delivery': 'failed',
                            'message': f'ADB{action}投递确认超时',
                        }
                    self._condition.wait(remaining)
                exit_code = self._acks.pop(sequence)
            if exit_code != 0:
                return {
                    'ok': False,
                    'method': 'adb_persistent',
                    'delivery': 'failed',
                    'message': f'ADB{action}命令执行失败（代码 {exit_code}）',
                }
        return {
            'ok': True,
            'method': 'adb_persistent',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'ADB持久通道已确认投递{action}到设备[{self.device_id}]{success_message}，界面效果待视觉验证',
        }

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300,
        hold_after_ms: int = 0,
    ) -> dict[str, Any]:
        # Android ``input swipe`` 只能在运动前保持，不能在终点单独停留。
        # 当需要终点保持时，将其纳入总时长作为标准 ADB 兼容降级；
        # scrcpy 控制通道会提供真正的 MOVE -> HOLD -> UP 语义。
        total_ms = max(0, int(duration_ms or 0)) + max(0, int(hold_after_ms or 0))
        command = (
            f'input swipe {int(start_x)} {int(start_y)} {int(end_x)} {int(end_y)} '
            f'{max(1, total_ms)}'
        )
        return self._execute_input_command(
            command,
            action='滑动',
            success_message=f'路径({int(start_x)},{int(start_y)})->({int(end_x)},{int(end_y)})',
            timeout_s=max(2.0, total_ms / 1000.0 + 1.5),
        )

    def keyevent(self, keycode: int) -> dict[str, Any]:
        return self._execute_input_command(
            f'input keyevent {int(keycode)}',
            action='按键',
            success_message=f' keycode={int(keycode)}',
        )

    def keycombination(self, *keycodes: int) -> dict[str, Any]:
        codes = [int(code) for code in keycodes]
        if not codes:
            return {'ok': False, 'method': 'adb_persistent', 'delivery': 'failed', 'message': '按键组合为空'}
        return self._execute_input_command(
            'input keycombination ' + ' '.join(str(code) for code in codes),
            action='组合按键',
            success_message=f' keycodes={codes}',
        )

    def text(self, value: str) -> dict[str, Any]:
        raw = str(value or '')
        # Android input text 并不具备可靠的 Unicode 语义。明确拒绝非 ASCII，
        # 交由 scrcpy UTF-8 控制通道处理，避免静默输入乱码。
        if any(ord(char) > 0x7F for char in raw):
            return {
                'ok': False,
                'method': 'adb_persistent',
                'delivery': 'unsupported',
                'message': 'ADB input text 不支持可靠 Unicode，需要 scrcpy 文本通道',
            }
        payload = raw.replace('%', '%25').replace(' ', '%s')
        return self._execute_input_command(
            f'input text {shlex.quote(payload)}',
            action='文本输入',
            success_message=f'长度={len(raw)}',
            timeout_s=max(2.0, len(raw) * 0.03 + 1.5),
        )

    def close(self):
        process = self._process
        self._process = None
        self._ready = False
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.write('exit\n')
                process.stdin.flush()
        except Exception:
            pass
        try:
            process.terminate()
        except Exception:
            pass


GLOBAL_TEMPLATE_CACHE = TemplateCache()


def get_android_input_session(context) -> PersistentAdbInputSession:
    """Return one input session per graph execution context and device."""

    device_id = str(getattr(context, 'device_id', '') or '').strip()
    existing = getattr(context, '_android_input_session', None)
    if isinstance(existing, PersistentAdbInputSession) and existing.device_id == device_id:
        return existing
    if existing is not None and hasattr(existing, 'close'):
        existing.close()
    session = PersistentAdbInputSession(device_id)
    context._android_input_session = session
    return session


def close_runtime_sessions(context):
    """Best-effort cleanup for transports owned by an executor context."""

    session = getattr(context, '_android_input_session', None)
    if session is not None and hasattr(session, 'close'):
        session.close()
    try:
        delattr(context, '_android_input_session')
    except AttributeError:
        pass
    video_session = getattr(context, '_android_video_session', None)
    if video_session is not None and hasattr(video_session, 'close'):
        video_session.close()
    try:
        delattr(context, '_android_video_session')
    except AttributeError:
        pass
    control_session = getattr(context, '_android_control_session', None)
    if control_session is not None and hasattr(control_session, 'close'):
        control_session.close()
    try:
        delattr(context, '_android_control_session')
    except AttributeError:
        pass


def create_visual_frame_stream(
    context,
    capture: Callable[[], tuple[Any, tuple[int, int, int, int]]],
    *,
    capture_region: tuple[int, int, int, int],
    workspace_size: tuple[int, int],
    performance_mode: str = 'auto',
    min_interval_ms: int = 0,
):
    """Select a frame provider without hiding capability downgrades."""

    requested = str(performance_mode or 'auto').strip().lower()
    if requested not in {'auto', 'standard', 'high_speed'}:
        requested = 'auto'
    is_android = bool(getattr(context, 'is_emulator', False)) or bool(
        getattr(context, 'is_android_target', False)
    )
    if is_android and requested != 'standard':
        try:
            from core.services.android_stream import validate_scrcpy_runtime

            available, detail = validate_scrcpy_runtime()
            if not available:
                raise RuntimeError(detail)
            return RecoveringAndroidFrameView(
                context,
                workspace_size=workspace_size,
                capture_region=capture_region,
                max_reconnects=int(
                    context.get_setting('android_stream_reconnect_attempts', 2)
                    if hasattr(context, 'get_setting') else 2
                ),
            )
        except Exception as exc:
            failed_session = getattr(context, '_android_video_session', None)
            if failed_session is not None and hasattr(failed_session, 'close'):
                failed_session.close()
            try:
                delattr(context, '_android_video_session')
            except AttributeError:
                pass
            if requested == 'high_speed':
                raise RuntimeError(f'Android高速采帧不可用: {exc}') from exc
            logger = getattr(context, 'log', None)
            if callable(logger):
                logger(f'[性能能力] Android高速采帧不可用，明确使用标准ADB采帧: {exc}', 'warning')
    def profiled_capture():
        image, region = capture()
        metadata = getattr(context, '_last_capture_info', None)
        if bool(getattr(context, 'is_emulator', False)) and not metadata:
            metadata = {'provider': 'adb_screencap'}
        return image, region, dict(metadata or {})

    stream = LatestFrameStream(profiled_capture, min_interval_ms=min_interval_ms)
    context._visual_frame_stream = stream
    return stream
