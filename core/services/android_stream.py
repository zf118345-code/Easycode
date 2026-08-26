"""Pinned scrcpy-based Android video stream for low-latency visual nodes."""

from __future__ import annotations

import hashlib
import os
import secrets
import socket
import struct
import subprocess
import threading
import time
from collections import deque
from typing import Any

import cv2

from core.services.runtime_session import FramePacket
from core.utils import resource_path


SCRCPY_SERVER_VERSION = '4.1'
SCRCPY_SERVER_NAME = f'scrcpy-server-v{SCRCPY_SERVER_VERSION}'
SCRCPY_SERVER_SHA256 = 'DEACB991ED2509715160FFDC7907E47B4160EB30D1566217E9047FD5B8850CAE'
DEVICE_SERVER_PATH = '/data/local/tmp/easycode-scrcpy-server.jar'


class AndroidStreamError(RuntimeError):
    pass


def scrcpy_server_path() -> str:
    return resource_path(os.path.join('native', 'android', SCRCPY_SERVER_NAME))


def validate_scrcpy_runtime() -> tuple[bool, str]:
    path = scrcpy_server_path()
    if not os.path.isfile(path):
        return False, f'缺少 {SCRCPY_SERVER_NAME}'
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError as exc:
        return False, f'无法读取 scrcpy-server: {exc}'
    if digest.hexdigest().upper() != SCRCPY_SERVER_SHA256:
        return False, 'scrcpy-server 校验值不匹配，已拒绝执行'
    try:
        import av  # noqa: F401
    except Exception as exc:
        return False, f'缺少 PyAV 解码器: {exc}'
    return True, 'scrcpy H.264 持续流可用'


def validate_scrcpy_control_runtime() -> tuple[bool, str]:
    """校验不依赖 PyAV 的 scrcpy 输入控制能力。"""
    path = scrcpy_server_path()
    if not os.path.isfile(path):
        return False, f'缺少 {SCRCPY_SERVER_NAME}'
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError as exc:
        return False, f'无法读取 scrcpy-server: {exc}'
    if digest.hexdigest().upper() != SCRCPY_SERVER_SHA256:
        return False, 'scrcpy-server 校验值不匹配，已拒绝执行'
    return True, 'scrcpy UTF-8 文本与触摸控制通道可用'


def _no_window_flags() -> dict[str, Any]:
    if os.name != 'nt':
        return {}
    return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}


class ScrcpyVideoSession:
    """One reusable video socket per graph execution and Android device."""

    def __init__(self, device_id: str, *, max_size: int = 1280, max_fps: int = 60):
        self.device_id = str(device_id or '').strip()
        self.max_size = max(0, int(max_size or 0))
        self.max_fps = max(1, min(120, int(max_fps or 60)))
        self._condition = threading.Condition()
        self._latest: FramePacket | None = None
        self._sequence = 0
        self._error: Exception | None = None
        self._started = False
        self._stop_event = threading.Event()
        self._server_process: subprocess.Popen | None = None
        self._socket: socket.socket | None = None
        self._control_socket: socket.socket | None = None
        self._listener: socket.socket | None = None
        self._container = None
        self._decoder_thread: threading.Thread | None = None
        self._log_thread: threading.Thread | None = None
        self._logs = deque(maxlen=30)
        self._forward_port: int | None = None
        self._reverse_socket_name: str | None = None
        self._control_lock = threading.Lock()

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            return int(probe.getsockname()[1])

    def _run_adb(self, args: list[str], timeout: float = 10.0):
        result = subprocess.run(
            ['adb', '-s', self.device_id, *args],
            capture_output=True,
            timeout=timeout,
            **_no_window_flags(),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or b'').decode(errors='ignore').strip()
            raise AndroidStreamError(detail or f'ADB 命令失败: {args}')
        return result

    def start(self) -> 'ScrcpyVideoSession':
        with self._condition:
            if self._started and self._decoder_thread and self._decoder_thread.is_alive():
                return self
            self._started = True
            self._error = None
            self._stop_event.clear()
        if not self.device_id:
            raise AndroidStreamError('Android高速流缺少设备序列号')
        valid, detail = validate_scrcpy_runtime()
        if not valid:
            raise AndroidStreamError(detail)

        try:
            try:
                self._run_adb(['push', '--sync', scrcpy_server_path(), DEVICE_SERVER_PATH], timeout=20)
            except AndroidStreamError:
                # Older platform-tools do not expose --sync. Compatibility
                # fallback remains an ADB file transfer, never another binary.
                self._run_adb(['push', scrcpy_server_path(), DEVICE_SERVER_PATH], timeout=20)
            # Match the official client's preferred topology: the host starts
            # listening first, then the device connects through ``adb reverse``.
            # Unlike adb-forward, this cannot report a successful TCP connect
            # before the device-side localabstract socket is actually ready.
            scid = secrets.randbelow(0x7FFFFFFF) + 1
            scid_hex = f'{scid:08x}'
            self._reverse_socket_name = f'scrcpy_{scid_hex}'
            self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(('127.0.0.1', 0))
            self._listener.listen(2)
            self._listener.settimeout(8.0)
            self._forward_port = int(self._listener.getsockname()[1])
            self._run_adb(
                ['reverse', f'localabstract:{self._reverse_socket_name}', f'tcp:{self._forward_port}'],
                timeout=5,
            )
            command = [
                'adb', '-s', self.device_id, 'shell',
                f'CLASSPATH={DEVICE_SERVER_PATH}',
                'app_process', '/', 'com.genymobile.scrcpy.Server', SCRCPY_SERVER_VERSION,
                f'scid={scid_hex}',
                'audio=false',
                'control=true',
                'cleanup=true',
                'raw_stream=true',
                f'max_size={self.max_size}',
                f'max_fps={self.max_fps}',
                'video_codec=h264',
            ]
            self._server_process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **_no_window_flags(),
            )
            self._log_thread = threading.Thread(target=self._drain_logs, name='easycode-scrcpy-log', daemon=True)
            self._log_thread.start()
            # scrcpy opens enabled sockets in the stable order video, audio,
            # control. Audio is disabled here, so accept video then control.
            self._socket = self._accept_reverse(close_listener=False)
            self._control_socket = self._accept_reverse(close_listener=True)
            self._decoder_thread = threading.Thread(target=self._decode, name='easycode-scrcpy-video', daemon=True)
            self._decoder_thread.start()
            return self
        except Exception:
            self.close()
            raise

    def _drain_logs(self):
        process = self._server_process
        if process is None or process.stdout is None:
            return
        for raw in iter(process.stdout.readline, b''):
            text = raw.decode(errors='ignore').strip()
            if text:
                self._logs.append(text)

    def _connect(self, port: int) -> socket.socket:
        deadline = time.monotonic() + 5.0
        last_error = None
        while time.monotonic() < deadline:
            if self._server_process is not None and self._server_process.poll() is not None:
                detail = ' | '.join(self._logs) or f'代码 {self._server_process.returncode}'
                raise AndroidStreamError(f'scrcpy-server 提前退出: {detail}')
            candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            candidate.settimeout(0.5)
            try:
                candidate.connect(('127.0.0.1', port))
                candidate.settimeout(None)
                candidate.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                return candidate
            except OSError as exc:
                last_error = exc
                candidate.close()
                time.sleep(0.05)
        raise AndroidStreamError(f'无法连接 scrcpy 视频通道: {last_error}')

    def _accept_reverse(self, *, close_listener: bool) -> socket.socket:
        listener = self._listener
        if listener is None:
            raise AndroidStreamError('scrcpy 反向隧道监听器未建立')
        try:
            candidate, _ = listener.accept()
        except socket.timeout as exc:
            detail = ' | '.join(self._logs)
            raise AndroidStreamError(f'等待 scrcpy 视频通道超时{f": {detail}" if detail else ""}') from exc
        finally:
            if not close_listener:
                listener = None
        if close_listener:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        candidate.settimeout(None)
        candidate.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return candidate

    @staticmethod
    def _touch_message(action: int, x: int, y: int, width: int, height: int) -> bytes:
        # Pinned scrcpy 4.1 internal protocol. Generic-finger input avoids
        # mouse-button semantics; pressure is 1.0 on DOWN and 0.0 on UP.
        pointer_id = 0xFFFFFFFFFFFFFFFE
        pressure = 0xFFFF if action == 0 else 0
        return struct.pack(
            '>BBQIIHHHII',
            2,  # SC_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT
            int(action),
            pointer_id,
            max(0, int(x)),
            max(0, int(y)),
            max(1, min(0xFFFF, int(width))),
            max(1, min(0xFFFF, int(height))),
            pressure,
            0,
            0,
        )

    def tap(self, x: int, y: int, width: int, height: int) -> dict[str, Any]:
        """Inject one Android touch without spawning a device-side ``input`` process."""

        self.start()
        control = self._control_socket
        if control is None:
            return {
                'ok': False,
                'method': 'scrcpy_control',
                'delivery': 'failed',
                'message': 'scrcpy 控制通道未建立',
            }
        # The video frame is authoritative for the current device rotation.
        # ``wm size`` often reports natural portrait dimensions even while a
        # game is landscape, which would otherwise reject or mis-scale taps.
        with self._condition:
            latest = self._latest
        if latest is not None:
            width = int(latest.region[2])
            height = int(latest.region[3])
        if not (0 <= int(x) < int(width) and 0 <= int(y) < int(height)):
            return {
                'ok': False,
                'method': 'scrcpy_control',
                'delivery': 'failed',
                'message': f'点击坐标({x},{y})超出Android画面 {width}x{height}',
            }
        try:
            down = self._touch_message(0, x, y, width, height)
            up = self._touch_message(1, x, y, width, height)
            with self._control_lock:
                control.sendall(down + up)
        except OSError as exc:
            return {
                'ok': False,
                'method': 'scrcpy_control',
                'delivery': 'failed',
                'message': f'scrcpy 点击投递失败: {exc}',
            }
        return {
            'ok': True,
            'method': 'scrcpy_control',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'scrcpy 控制通道已投递设备[{self.device_id}]坐标({int(x)},{int(y)})，界面效果待视觉验证',
        }

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        width: int,
        height: int,
        *,
        duration_ms: int = 300,
        hold_before_ms: int = 0,
        hold_after_ms: int = 0,
        steps: int = 12,
        stop_check=None,
    ) -> dict[str, Any]:
        """通过 scrcpy 发送 DOWN -> MOVE* -> HOLD -> UP，精确支持终点保持。"""
        self.start()
        control = self._control_socket
        if control is None:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': 'scrcpy 控制通道未建立'}
        with self._condition:
            latest = self._latest
        if latest is not None:
            width, height = int(latest.region[2]), int(latest.region[3])
        points = (int(start_x), int(start_y), int(end_x), int(end_y))
        if not all((0 <= points[index] < (width if index % 2 == 0 else height)) for index in range(4)):
            return {
                'ok': False,
                'method': 'scrcpy_control',
                'delivery': 'failed',
                'message': f'滑动路径{points}超出Android画面 {width}x{height}',
            }
        count = max(1, min(240, int(steps or 1)))
        step_delay = max(0, int(duration_ms or 0)) / 1000.0 / count

        def interrupted() -> bool:
            return bool(stop_check and stop_check())

        def wait_interruptibly(milliseconds: int) -> bool:
            deadline = time.monotonic() + max(0, int(milliseconds or 0)) / 1000.0
            while time.monotonic() < deadline:
                if interrupted():
                    return False
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            return not interrupted()

        try:
            with self._control_lock:
                control.sendall(self._touch_message(0, start_x, start_y, width, height))
                if not wait_interruptibly(hold_before_ms):
                    return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '滑动已被停止'}
                for index in range(1, count + 1):
                    if interrupted():
                        return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '滑动已被停止'}
                    ratio = index / count
                    x = round(start_x + (end_x - start_x) * ratio)
                    y = round(start_y + (end_y - start_y) * ratio)
                    control.sendall(self._touch_message(2, x, y, width, height))
                    if step_delay:
                        time.sleep(step_delay)
                if not wait_interruptibly(hold_after_ms):
                    return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '滑动已被停止'}
                control.sendall(self._touch_message(1, end_x, end_y, width, height))
        except OSError as exc:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy 滑动投递失败: {exc}'}
        finally:
            if interrupted():
                try:
                    with self._control_lock:
                        control.sendall(self._touch_message(1, end_x, end_y, width, height))
                except OSError:
                    pass
        return {
            'ok': True,
            'method': 'scrcpy_control',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'scrcpy 滑动已投递设备[{self.device_id}] ({start_x},{start_y})->({end_x},{end_y})，效果待视觉验证',
        }

    def swipe_path(
        self,
        path_points: list[dict[str, Any]],
        width: int,
        height: int,
        *,
        easing: str = 'linear',
        stop_check=None,
    ) -> dict[str, Any]:
        """通过一个连续触摸序列执行最多32点的拖拽路径。"""
        self.start()
        control = self._control_socket
        if control is None:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': 'scrcpy 控制通道未建立'}
        with self._condition:
            latest = self._latest
        if latest is not None:
            width, height = int(latest.region[2]), int(latest.region[3])
        normalized = []
        for index, item in enumerate((path_points or [])[:32]):
            point = item.get('point') if isinstance(item, dict) else None
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'路径第{index + 1}个点无效'}
            x, y = int(point[0]), int(point[1])
            if not (0 <= x < width and 0 <= y < height):
                return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'路径点({x},{y})超出Android画面 {width}x{height}'}
            normalized.append({'point': (x, y), 'move_ms': max(0, int(item.get('move_ms', 0) or 0)), 'hold_ms': max(0, int(item.get('hold_ms', 0) or 0))})
        if not normalized:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': '拖拽路径为空'}

        def interrupted():
            return bool(stop_check and stop_check())

        def wait_interruptibly(milliseconds):
            deadline = time.monotonic() + max(0, milliseconds) / 1000.0
            while time.monotonic() < deadline:
                if interrupted():
                    return False
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            return not interrupted()

        def curve(value):
            return value * value * (3 - 2 * value) if easing == 'ease_in_out' else value

        final_x, final_y = normalized[-1]['point']
        try:
            with self._control_lock:
                start_x, start_y = normalized[0]['point']
                control.sendall(self._touch_message(0, start_x, start_y, width, height))
                if not wait_interruptibly(normalized[0]['hold_ms']):
                    return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
                previous = normalized[0]['point']
                for segment in normalized[1:]:
                    target_x, target_y = segment['point']
                    move_ms = segment['move_ms']
                    count = max(1, min(240, round(max(16, move_ms) / 16)))
                    delay = move_ms / 1000.0 / count if move_ms else 0
                    for index in range(1, count + 1):
                        if interrupted():
                            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
                        ratio = curve(index / count)
                        x = round(previous[0] + (target_x - previous[0]) * ratio)
                        y = round(previous[1] + (target_y - previous[1]) * ratio)
                        control.sendall(self._touch_message(2, x, y, width, height))
                        if delay:
                            time.sleep(delay)
                    if not wait_interruptibly(segment['hold_ms']):
                        return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'cancelled', 'message': '拖拽已被停止'}
                    previous = segment['point']
                control.sendall(self._touch_message(1, final_x, final_y, width, height))
        except OSError as exc:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy 路径拖拽投递失败: {exc}'}
        finally:
            if interrupted():
                try:
                    with self._control_lock:
                        control.sendall(self._touch_message(1, final_x, final_y, width, height))
                except OSError:
                    pass
        return {'ok': True, 'method': 'scrcpy_control', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'scrcpy 已连续投递 {len(normalized)} 个路径点，效果待视觉验证'}

    def inject_text(self, value: str, *, paste: bool = True) -> dict[str, Any]:
        """使用 scrcpy UTF-8 剪贴板协议输入文本，支持中文且不占用PC键盘。"""
        self.start()
        control = self._control_socket
        if control is None:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': 'scrcpy 控制通道未建立'}
        encoded = str(value or '').encode('utf-8')
        if len(encoded) > 1024 * 1024:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'blocked', 'message': '文本超过1MiB安全上限'}
        # scrcpy 4.1 SC_CONTROL_MSG_TYPE_SET_CLIPBOARD:
        # type:u8, sequence:u64, paste:u8, length:u32, UTF-8 bytes.
        message = struct.pack('>BQBI', 9, time.monotonic_ns() & 0xFFFFFFFFFFFFFFFF, 1 if paste else 0, len(encoded)) + encoded
        try:
            with self._control_lock:
                control.sendall(message)
        except OSError as exc:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy 文本投递失败: {exc}'}
        return {
            'ok': True,
            'method': 'scrcpy_control',
            'delivery': 'delivered_unverified',
            'verified': False,
            'message': f'scrcpy UTF-8 文本已投递设备[{self.device_id}]，长度={len(str(value or ""))}，效果待验证',
        }

    def keyevent(self, keycode: int, *, metastate: int = 0) -> dict[str, Any]:
        self.start()
        control = self._control_socket
        if control is None:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': 'scrcpy 控制通道未建立'}
        try:
            # type:u8, action:u8, keycode:u32, repeat:u32, metastate:u32
            down = struct.pack('>BBIII', 0, 0, int(keycode), 0, int(metastate))
            up = struct.pack('>BBIII', 0, 1, int(keycode), 0, int(metastate))
            with self._control_lock:
                control.sendall(down + up)
        except OSError as exc:
            return {'ok': False, 'method': 'scrcpy_control', 'delivery': 'failed', 'message': f'scrcpy 按键投递失败: {exc}'}
        return {'ok': True, 'method': 'scrcpy_control', 'delivery': 'delivered_unverified', 'verified': False, 'message': f'scrcpy keycode={int(keycode)} meta={int(metastate)} 已投递'}

    def _decode(self):
        try:
            import av

            if self._socket is None:
                raise AndroidStreamError('scrcpy 视频 Socket 未建立')
            # Feed the elementary H.264 stream directly into the codec parser.
            # ``av.open()`` performs demuxer probing and may wait for substantially
            # more data on a quiet/static screen; CodecContext.parse() emits the
            # first decodable access unit without that startup buffer.
            decoder = av.CodecContext.create('h264', 'r')
            while not self._stop_event.is_set():
                chunk = self._socket.recv(256 * 1024)
                if not chunk:
                    process_code = self._server_process.poll() if self._server_process is not None else None
                    logs = ' | '.join(self._logs)
                    suffix = f'；server={process_code}'
                    if logs:
                        suffix += f'；日志={logs}'
                    raise AndroidStreamError(f'scrcpy 视频流已结束{suffix}')
                for packet in decoder.parse(chunk):
                    for frame in decoder.decode(packet):
                        if self._stop_event.is_set():
                            return
                        converted_started = time.monotonic_ns()
                        image = frame.to_ndarray(format='rgb24')
                        completed_ns = time.monotonic_ns()
                        height, width = image.shape[:2]
                        with self._condition:
                            self._sequence += 1
                            self._latest = FramePacket(
                                image=image,
                                region=(0, 0, int(width), int(height)),
                                sequence=self._sequence,
                                captured_at_ns=completed_ns,
                                capture_duration_ms=(completed_ns - converted_started) / 1_000_000.0,
                                provider='scrcpy_stream',
                            )
                            self._condition.notify_all()
        except Exception as exc:
            if not self._stop_event.is_set():
                with self._condition:
                    self._error = exc
                    self._condition.notify_all()

    def next(self, after_sequence: int = 0, timeout_s: float | None = None) -> FramePacket:
        self.start()
        deadline = None if timeout_s is None else time.monotonic() + max(0.0, timeout_s)
        with self._condition:
            while True:
                if self._latest is not None and self._latest.sequence > after_sequence:
                    return self._latest
                if self._error is not None:
                    raise AndroidStreamError(f'Android高速画面流失败: {self._error}') from self._error
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError('等待 Android 高速画面超时')
                self._condition.wait(remaining)

    def close(self):
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        container = self._container
        self._container = None
        if container is not None:
            try:
                container.close()
            except Exception:
                pass
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        control_socket = self._control_socket
        self._control_socket = None
        if control_socket is not None:
            try:
                control_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                control_socket.close()
            except Exception:
                pass
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass
        process = self._server_process
        self._server_process = None
        if process is not None:
            try:
                process.terminate()
            except Exception:
                pass
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except Exception:
                    pass
        if self._reverse_socket_name is not None and self.device_id:
            try:
                subprocess.run(
                    [
                        'adb', '-s', self.device_id, 'reverse', '--remove',
                        f'localabstract:{self._reverse_socket_name}',
                    ],
                    capture_output=True,
                    timeout=3,
                    **_no_window_flags(),
                )
            except Exception:
                pass
        self._forward_port = None
        self._reverse_socket_name = None
        self._started = False
        decoder_thread = self._decoder_thread
        self._decoder_thread = None
        if decoder_thread and decoder_thread.is_alive() and decoder_thread is not threading.current_thread():
            decoder_thread.join(timeout=0.5)


class ScrcpyControlSession(ScrcpyVideoSession):
    """不启动视频解码的轻量 scrcpy 控制会话。"""

    def __init__(self, device_id: str):
        super().__init__(device_id, max_size=0, max_fps=1)

    def start(self) -> 'ScrcpyControlSession':
        with self._condition:
            if self._started and self._control_socket is not None:
                return self
            self._started = True
            self._error = None
            self._stop_event.clear()
        if not self.device_id:
            raise AndroidStreamError('Android控制通道缺少设备序列号')
        valid, detail = validate_scrcpy_control_runtime()
        if not valid:
            raise AndroidStreamError(detail)
        try:
            try:
                self._run_adb(['push', '--sync', scrcpy_server_path(), DEVICE_SERVER_PATH], timeout=20)
            except AndroidStreamError:
                self._run_adb(['push', scrcpy_server_path(), DEVICE_SERVER_PATH], timeout=20)
            scid = secrets.randbelow(0x7FFFFFFF) + 1
            scid_hex = f'{scid:08x}'
            self._reverse_socket_name = f'scrcpy_{scid_hex}'
            self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._listener.bind(('127.0.0.1', 0))
            self._listener.listen(1)
            self._listener.settimeout(8.0)
            self._forward_port = int(self._listener.getsockname()[1])
            self._run_adb(['reverse', f'localabstract:{self._reverse_socket_name}', f'tcp:{self._forward_port}'], timeout=5)
            command = [
                'adb', '-s', self.device_id, 'shell',
                f'CLASSPATH={DEVICE_SERVER_PATH}',
                'app_process', '/', 'com.genymobile.scrcpy.Server', SCRCPY_SERVER_VERSION,
                f'scid={scid_hex}', 'video=false', 'audio=false', 'control=true', 'cleanup=true',
            ]
            self._server_process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **_no_window_flags(),
            )
            self._log_thread = threading.Thread(target=self._drain_logs, name='easycode-scrcpy-control-log', daemon=True)
            self._log_thread.start()
            self._control_socket = self._accept_reverse(close_listener=True)
            return self
        except Exception:
            self.close()
            raise


class AndroidFrameView:
    """Workspace-sized/cropped view over a reusable device video stream."""

    def __init__(
        self,
        session: ScrcpyVideoSession,
        *,
        workspace_size: tuple[int, int],
        capture_region: tuple[int, int, int, int],
    ):
        self.session = session
        self.workspace_size = tuple(int(value) for value in workspace_size)
        self.capture_region = tuple(int(value) for value in capture_region)
        self.provider = 'scrcpy_stream'

    def start(self):
        self.session.start()
        return self

    def next(self, after_sequence: int = 0, timeout_s: float | None = None) -> FramePacket:
        packet = self.session.next(after_sequence, timeout_s)
        image = packet.image
        work_w, work_h = self.workspace_size
        if image.shape[1] != work_w or image.shape[0] != work_h:
            image = cv2.resize(image, (work_w, work_h), interpolation=cv2.INTER_LINEAR)
        x, y, width, height = self.capture_region
        image = image[y : y + height, x : x + width]
        return FramePacket(
            image=image,
            region=self.capture_region,
            sequence=packet.sequence,
            captured_at_ns=packet.captured_at_ns,
            capture_duration_ms=packet.capture_duration_ms,
            provider=packet.provider,
        )

    def stop(self, join_timeout_s: float = 0.0):
        # The graph executor owns the reusable device session.
        return None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        return None


def get_android_video_session(context, workspace_size: tuple[int, int]) -> ScrcpyVideoSession:
    device_id = str(getattr(context, 'device_id', '') or '').strip()
    existing = getattr(context, '_android_video_session', None)
    if isinstance(existing, ScrcpyVideoSession) and existing.device_id == device_id:
        return existing
    if existing is not None and hasattr(existing, 'close'):
        existing.close()
    session = ScrcpyVideoSession(device_id, max_size=max(workspace_size), max_fps=60)
    setattr(context, '_android_video_session', session)
    return session


def get_android_control_session(context) -> ScrcpyVideoSession:
    """优先复用视频会话，否则创建不解码画面的轻量控制会话。"""
    device_id = str(getattr(context, 'device_id', '') or '').strip()
    video = getattr(context, '_android_video_session', None)
    if isinstance(video, ScrcpyVideoSession) and video.device_id == device_id:
        return video
    existing = getattr(context, '_android_control_session', None)
    if isinstance(existing, ScrcpyControlSession) and existing.device_id == device_id:
        return existing
    if existing is not None and hasattr(existing, 'close'):
        existing.close()
    session = ScrcpyControlSession(device_id)
    setattr(context, '_android_control_session', session)
    return session
