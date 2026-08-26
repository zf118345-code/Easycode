"""工作面板逐帧录制。

按用户选择保存全部帧、变化帧或诊断事件帧；所有落盘帧均为无损 PNG，
不覆盖且不自动删除。录制目录同时写入逐帧时间索引和 SHA-256 校验信息。
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import queue
import shutil
import threading
import time
import uuid
from datetime import datetime
from typing import Any

import numpy as np

from core.security import assert_safe_path, atomic_write_json

logger = logging.getLogger(__name__)


class FrameRecordingError(RuntimeError):
    """录制无法安全启动或继续。"""


class FrameRecordingService:
    MIN_FREE_BYTES = 256 * 1024 * 1024
    MAX_CONSECUTIVE_CAPTURE_ERRORS = 5
    DEFAULT_QUEUE_CAPACITY = 96

    def __init__(self):
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._writer_thread: threading.Thread | None = None
        self._write_queue: queue.Queue | None = None
        self._writer_error: Exception | None = None
        self._context: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._last_publish = 0.0
        self._finishing = False
        self._previous_signature = None
        self._pending_event: dict[str, Any] | None = None
        self._state = self._empty_state()
        self._subscribers: list[queue.Queue] = []

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            'active': False,
            'status': 'idle',
            'project_path': '',
            'session_id': '',
            'output_dir': '',
            'frame_count': 0,
            'started_at': '',
            'stopped_at': '',
            'last_capture_at': '',
            'last_frame': '',
            'last_error': '',
            'stop_reason': '',
            'target_title': '',
            'capture_backend': '',
            'elapsed_ms': 0,
            'average_fps': 0.0,
            'capture_count': 0,
            'queue_depth': 0,
            'queue_capacity': 0,
            'backpressure_count': 0,
            'write_lag_ms': 0.0,
            'disk_bytes': 0,
            'target_fps': 0.0,
            'recording_mode': 'lossless_all_frames',
            'skipped_frame_count': 0,
            'change_threshold': 0.006,
            'max_session_bytes': 0,
            'screen_region': [],
            'event_count': 0,
        }

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
        if state['active'] and state.get('_started_monotonic'):
            elapsed = max(0.0, time.monotonic() - float(state['_started_monotonic']))
            state['elapsed_ms'] = int(elapsed * 1000)
            state['average_fps'] = round(state['frame_count'] / elapsed, 2) if elapsed > 0 else 0.0
        state.pop('_started_monotonic', None)
        return state

    def subscribe(self) -> queue.Queue:
        subscriber = queue.Queue()
        with self._lock:
            self._subscribers.append(subscriber)
        subscriber.put_nowait({'event': 'state', **self.get_state()})
        return subscriber

    def mark_event(self, label: str = '手动标记') -> dict[str, Any]:
        clean_label = str(label or '手动标记').strip()[:120] or '手动标记'
        with self._lock:
            if not self._state.get('active'):
                raise FrameRecordingError('当前没有正在进行的逐帧录制')
            self._pending_event = {
                'type': 'manual',
                'label': clean_label,
                'marked_at': datetime.now().astimezone().isoformat(timespec='milliseconds'),
            }
        self._publish('diagnostic_marker', force=True)
        return {'status': 'success', 'label': clean_label}

    def unsubscribe(self, subscriber: queue.Queue):
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def _publish(self, event: str, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_publish < 0.25:
            return
        self._last_publish = now
        payload = {'event': event, **self.get_state()}
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except Exception:
                pass

    @staticmethod
    def _load_context(project_path: str) -> dict[str, Any]:
        context_path = os.path.join(project_path, 'context.json')
        if not os.path.isfile(context_path):
            raise FrameRecordingError('项目尚未配置工作面板，请先在顶部选择工作面板')
        try:
            from core.services.workspace_service import WorkspaceService

            context = WorkspaceService.load_runtime_context(project_path)
        except Exception as exc:
            raise FrameRecordingError(f'工作面板配置读取失败: {exc}') from exc
        if not isinstance(context, dict):
            raise FrameRecordingError('工作面板配置格式无效')
        return context

    @staticmethod
    def _activate_target(context: dict[str, Any]) -> tuple[int | None, str]:
        """激活绑定窗口并验证它确实成为前台窗口。桌面模式无需激活。"""
        work_mode = str(context.get('work_mode') or ('window' if context.get('window_title') else 'desktop'))
        if work_mode != 'window' or not context.get('window_title'):
            return None, 'foreground_screen'

        import win32api
        import win32con
        import win32gui
        import win32process

        from core.services.workspace_service import WorkspaceService

        hwnd = WorkspaceService._resolve_context_window(context)
        target_root = win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd
        attached: list[tuple[int, int]] = []
        try:
            current_tid = int(win32api.GetCurrentThreadId())
            target_tid, _ = win32process.GetWindowThreadProcessId(target_root)
            foreground = win32gui.GetForegroundWindow()
            foreground_tid = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
            for first, second in ((current_tid, int(target_tid)), (current_tid, int(foreground_tid))):
                if second and first != second:
                    try:
                        win32process.AttachThreadInput(first, second, True)
                        attached.append((first, second))
                    except Exception:
                        pass
            if win32gui.IsIconic(target_root):
                win32gui.ShowWindow(target_root, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                target_root,
                win32con.HWND_TOP,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
            )
            win32gui.BringWindowToTop(target_root)
            win32gui.SetForegroundWindow(target_root)
        except Exception as exc:
            raise FrameRecordingError(f'无法激活工作面板窗口: {exc}') from exc
        finally:
            for first, second in reversed(attached):
                try:
                    win32process.AttachThreadInput(first, second, False)
                except Exception:
                    pass

        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            foreground = win32gui.GetForegroundWindow()
            foreground_root = win32gui.GetAncestor(foreground, getattr(win32con, 'GA_ROOT', 2)) if foreground else 0
            if int(foreground_root or foreground or 0) == int(target_root):
                return int(hwnd), 'foreground_screen'
            time.sleep(0.02)
        raise FrameRecordingError('工作面板未能成为前台窗口，已阻止录制以免记录错误画面')

    @staticmethod
    def _capture_image(context: dict[str, Any]):
        """高速捕获当前可见的裁剪工作区；窗口身份不符时拒绝录入其他画面。"""
        import win32con
        import win32gui

        from core.services import screenshot_service
        from core.services.workspace_service import WorkspaceService

        off_top = int(context.get('offset_top', 0) or 0)
        off_bottom = int(context.get('offset_bottom', 0) or 0)
        off_left = int(context.get('offset_left', 0) or 0)
        off_right = int(context.get('offset_right', 0) or 0)
        work_mode = str(context.get('work_mode') or ('window' if context.get('window_title') else 'desktop'))

        if work_mode == 'window' and context.get('window_title'):
            hwnd = WorkspaceService._resolve_context_window(context)
            target_root = win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd
            foreground = win32gui.GetForegroundWindow()
            foreground_root = (
                win32gui.GetAncestor(foreground, getattr(win32con, 'GA_ROOT', 2)) if foreground else 0
            )
            if int(foreground_root or foreground or 0) != int(target_root):
                raise FrameRecordingError('工作面板已失去前台焦点，已停止录制以免混入其他窗口画面')

            client = win32gui.GetClientRect(hwnd)
            left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
            right, bottom = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
            region = (left + off_left, top + off_top, right - off_right, bottom - off_bottom)
        else:
            import pyautogui

            screen_width, screen_height = pyautogui.size()
            region = (off_left, off_top, screen_width - off_right, screen_height - off_bottom)

        if region[2] <= region[0] or region[3] <= region[1]:
            raise FrameRecordingError(f'裁剪后的工作面板区域无效: {region}')
        clamped = screenshot_service._clamp_region(region)
        if clamped is None or tuple(clamped) != tuple(region):
            raise FrameRecordingError('裁剪后的工作面板未完整显示在屏幕内，已停止录制以免保存错误区域')
        return screenshot_service.capture(region=region)

    @staticmethod
    def _enable_escape() -> dict:
        from core.services import capture_mode

        capture_mode.stop_mode()
        return capture_mode.set_recording_escape_enabled(True)

    @staticmethod
    def _disable_escape():
        try:
            from core.services import capture_mode

            capture_mode.set_recording_escape_enabled(False)
        except Exception:
            logger.exception('释放录制 Esc 热键失败')

    @staticmethod
    def _normalize_options(options: dict[str, Any] | None) -> dict[str, Any]:
        raw = options if isinstance(options, dict) else {}
        try:
            target_fps = max(0.0, min(240.0, float(raw.get('target_fps') or 0)))
        except (TypeError, ValueError):
            target_fps = 0.0
        try:
            capacity = max(8, min(512, int(raw.get('queue_capacity') or FrameRecordingService.DEFAULT_QUEUE_CAPACITY)))
        except (TypeError, ValueError):
            capacity = FrameRecordingService.DEFAULT_QUEUE_CAPACITY
        mode = str(raw.get('recording_mode') or 'lossless_all_frames').strip().lower()
        if mode not in {'lossless_all_frames', 'changed_frames', 'diagnostic_events'}:
            mode = 'lossless_all_frames'
        try:
            change_threshold = max(0.0001, min(1.0, float(raw.get('change_threshold') or 0.006)))
        except (TypeError, ValueError):
            change_threshold = 0.006
        try:
            max_session_bytes = max(0, int(raw.get('max_session_bytes') or 0))
        except (TypeError, ValueError):
            max_session_bytes = 0
        return {
            'target_fps': target_fps,
            'queue_capacity': capacity,
            'recording_mode': mode,
            'change_threshold': change_threshold,
            'max_session_bytes': max_session_bytes,
        }

    def start(self, project_path: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """启动录制；返回前已保存首帧，避免菜单点击后存在无保护空窗。"""
        try:
            from core.services.capture_session_service import capture_session_service

            if capture_session_service.is_capture_active():
                raise FrameRecordingError('请先退出截图捕获模式')
        except FrameRecordingError:
            raise
        except Exception:
            pass
        with self._lifecycle_lock:
            current = self.get_state()
            if current['active']:
                if os.path.normcase(current['project_path']) == os.path.normcase(os.path.abspath(project_path or '')):
                    return current
                raise FrameRecordingError('已有其他项目正在逐帧录制，请先按 Esc 停止')

            project_path = os.path.abspath(str(project_path or '').strip())
            if not project_path or not os.path.isdir(project_path):
                raise FrameRecordingError('项目路径不存在，无法开始逐帧录制')
            context = self._load_context(project_path)
            normalized_options = self._normalize_options(options)
            session_id = f'frame_recording_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:6]}'
            recordings_root = assert_safe_path(project_path, os.path.join(project_path, 'recordings'))
            output_dir = assert_safe_path(project_path, os.path.join(recordings_root, session_id))
            os.makedirs(output_dir, exist_ok=False)

            stop_event = threading.Event()
            started_at = datetime.now().astimezone().isoformat(timespec='milliseconds')
            with self._lock:
                self._context = dict(context)
                self._options = normalized_options
                self._stop_event = stop_event
                self._thread = None
                self._writer_thread = None
                self._write_queue = queue.Queue(maxsize=normalized_options['queue_capacity'])
                self._writer_error = None
                self._previous_signature = None
                self._pending_event = None
                self._state = {
                    **self._empty_state(),
                    'active': True,
                    'status': 'starting',
                    'project_path': project_path,
                    'session_id': session_id,
                    'output_dir': output_dir,
                    'started_at': started_at,
                    'target_title': str(context.get('window_title') or 'Windows 桌面'),
                    'capture_backend': 'pending',
                    'queue_capacity': normalized_options['queue_capacity'],
                    'target_fps': normalized_options['target_fps'],
                    'recording_mode': normalized_options['recording_mode'],
                    'change_threshold': normalized_options['change_threshold'],
                    'max_session_bytes': normalized_options['max_session_bytes'],
                    '_started_monotonic': time.monotonic(),
                }
            self._write_manifest(final=False)

            try:
                if shutil.disk_usage(output_dir).free < self.MIN_FREE_BYTES:
                    raise FrameRecordingError('磁盘剩余空间低于 256MB，已阻止录制；不会删除既有录制')
                escape = self._enable_escape()
                if not escape.get('ok'):
                    raise FrameRecordingError(f'无法优先接管 Esc，已阻止录制: {escape.get("message", "未知错误")}')
                _, backend = self._activate_target(context)
                with self._lock:
                    self._state['status'] = 'recording'
                    self._state['capture_backend'] = backend
                if stop_event.is_set():
                    self._finish('stopped', '')
                    return self.get_state()
                self._capture_and_save()
                if stop_event.is_set():
                    self._finish('stopped', '')
                    return self.get_state()
                writer_thread = threading.Thread(
                    target=self._writer_loop,
                    daemon=True,
                    name=f'frame-writer-{session_id[-6:]}',
                )
                thread = threading.Thread(
                    target=self._record_loop,
                    daemon=True,
                    name=f'frame-recorder-{session_id[-6:]}',
                )
                with self._lock:
                    self._writer_thread = writer_thread
                    self._thread = thread
                writer_thread.start()
                thread.start()
                self._publish('started', force=True)
                return self.get_state()
            except Exception as exc:
                self._finish('error', str(exc))
                if isinstance(exc, FrameRecordingError):
                    raise
                raise FrameRecordingError(str(exc)) from exc

    def _screen_region_for_image(self, context: dict[str, Any], image) -> list[int]:
        """Best-effort placement metadata; it never changes the recorded pixels."""
        try:
            work_mode = str(context.get('work_mode') or ('window' if context.get('window_title') else 'desktop'))
            off_top = int(context.get('offset_top', 0) or 0)
            off_left = int(context.get('offset_left', 0) or 0)
            if work_mode == 'window' and context.get('window_title'):
                import win32gui
                from core.services.workspace_service import WorkspaceService

                hwnd = WorkspaceService._resolve_context_window(context)
                client = win32gui.GetClientRect(hwnd)
                left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
                region = [left + off_left, top + off_top, left + off_left + image.width, top + off_top + image.height]
            else:
                region = [off_left, off_top, off_left + image.width, off_top + image.height]
            return [int(value) for value in region]
        except Exception:
            return [0, 0, int(image.width), int(image.height)]

    def _capture_packet(self) -> dict[str, Any]:
        with self._lock:
            context = dict(self._context)
        image = self._capture_image(context).convert('RGB')
        signature = np.asarray(image.convert('L').resize((64, 36)), dtype=np.float32)
        with self._lock:
            frame_index = int(self._state['capture_count']) + 1
            self._state['capture_count'] = frame_index
            previous = self._previous_signature
            self._previous_signature = signature
            event = self._pending_event
            self._pending_event = None
        change_score = 1.0 if previous is None else float(np.mean(np.abs(signature - previous)) / 255.0)
        return {
            'index': frame_index,
            'image': image,
            'captured_at': datetime.now().astimezone().isoformat(timespec='milliseconds'),
            'captured_monotonic': time.monotonic(),
            'timestamp_ns': time.time_ns(),
            'screen_region': self._screen_region_for_image(context, image),
            'change_score': round(change_score, 6),
            'event': event,
        }

    def _write_packet(self, packet: dict[str, Any], index_file=None):
        with self._lock:
            output_dir = self._state['output_dir']
        if not output_dir:
            raise FrameRecordingError('录制输出目录未初始化')
        image = packet['image']
        capture_index = int(packet['index'])
        with self._lock:
            frame_index = int(self._state['frame_count']) + 1
        timestamp_ns = int(packet['timestamp_ns'])
        file_name = f'frame_{frame_index:08d}_{timestamp_ns}.png'
        file_path = assert_safe_path(output_dir, os.path.join(output_dir, file_name))
        # PNG 为无损格式；低压缩级别优先保证连续捕获速度，不牺牲像素细节。
        image.save(file_path, format='PNG', compress_level=1)
        digest = hashlib.sha256()
        with open(file_path, 'rb') as saved_stream:
            for chunk in iter(lambda: saved_stream.read(1024 * 1024), b''):
                digest.update(chunk)
        record = {
            'index': frame_index,
            'capture_index': capture_index,
            'file': file_name,
            'captured_at': packet['captured_at'],
            'timestamp_ns': timestamp_ns,
            'width': image.width,
            'height': image.height,
            'bytes': os.path.getsize(file_path),
            'screen_region': list(packet.get('screen_region') or [0, 0, image.width, image.height]),
            'change_score': float(packet.get('change_score') or 0.0),
            'sha256': digest.hexdigest(),
        }
        if packet.get('event'):
            record['event'] = dict(packet['event'])
        owns_index = index_file is None
        if owns_index:
            index_file = open(os.path.join(output_dir, 'frames.jsonl'), 'a', encoding='utf-8', buffering=1)
        try:
            index_file.write(json.dumps(record, ensure_ascii=False) + '\n')
            if owns_index:
                index_file.flush()
        finally:
            if owns_index:
                index_file.close()
        with self._lock:
            self._state['frame_count'] = frame_index
            self._state['last_capture_at'] = record['captured_at']
            self._state['last_frame'] = file_name
            self._state['screen_region'] = record['screen_region']
            self._state['disk_bytes'] = int(self._state.get('disk_bytes') or 0) + int(record['bytes'])
            self._state['write_lag_ms'] = round(max(0.0, time.monotonic() - packet['captured_monotonic']) * 1000, 2)
            if record.get('event'):
                self._state['event_count'] = int(self._state.get('event_count') or 0) + 1
        self._publish('frame')

    def _capture_and_save(self):
        self._write_packet(self._capture_packet())

    def _writer_loop(self):
        write_queue = self._write_queue
        if write_queue is None:
            return
        with self._lock:
            output_dir = self._state['output_dir']
        try:
            with open(os.path.join(output_dir, 'frames.jsonl'), 'a', encoding='utf-8', buffering=1) as index_file:
                while True:
                    packet = write_queue.get()
                    try:
                        if packet is None:
                            return
                        self._write_packet(packet, index_file=index_file)
                    finally:
                        write_queue.task_done()
                        with self._lock:
                            self._state['queue_depth'] = write_queue.qsize()
        except Exception as exc:
            with self._lock:
                self._writer_error = exc
                self._state['last_error'] = str(exc)
            stop = self._stop_event
            if stop:
                stop.set()

    def _record_loop(self):
        consecutive_errors = 0
        final_error = ''
        final_status = 'stopped'
        try:
            last_disk_check = 0.0
            while True:
                stop = self._stop_event
                if stop is None or stop.is_set():
                    break
                with self._lock:
                    output_dir = self._state['output_dir']
                    writer_error = self._writer_error
                    target_fps = float(self._state.get('target_fps') or 0)
                    recording_mode = str(self._state.get('recording_mode') or 'lossless_all_frames')
                    change_threshold = float(self._state.get('change_threshold') or 0.006)
                    max_session_bytes = int(self._state.get('max_session_bytes') or 0)
                if writer_error:
                    raise FrameRecordingError(f'录制写入线程失败: {writer_error}')
                now = time.monotonic()
                if now - last_disk_check >= 1.0:
                    last_disk_check = now
                    if shutil.disk_usage(output_dir).free < self.MIN_FREE_BYTES:
                        raise FrameRecordingError('磁盘剩余空间低于 256MB，已停止录制；已有帧全部保留')
                try:
                    capture_started = time.monotonic()
                    packet = self._capture_packet()
                    if (
                        recording_mode in {'changed_frames', 'diagnostic_events'}
                        and int(packet['index']) > 1
                        and float(packet.get('change_score') or 0.0) < change_threshold
                        and not (recording_mode == 'diagnostic_events' and packet.get('event'))
                    ):
                        with self._lock:
                            self._state['skipped_frame_count'] = int(self._state.get('skipped_frame_count') or 0) + 1
                        if target_fps > 0:
                            remaining = (1.0 / target_fps) - (time.monotonic() - capture_started)
                            if remaining > 0 and stop.wait(remaining):
                                break
                        continue
                    if max_session_bytes > 0:
                        with self._lock:
                            used_bytes = int(self._state.get('disk_bytes') or 0)
                        if used_bytes >= max_session_bytes:
                            raise FrameRecordingError(
                                f'录制会话已达到空间上限 {max_session_bytes} 字节，已停止且不会删除已有帧'
                            )
                    write_queue = self._write_queue
                    if write_queue is None:
                        raise FrameRecordingError('录制写入队列未初始化')
                    while True:
                        try:
                            write_queue.put(packet, timeout=0.1)
                            with self._lock:
                                self._state['queue_depth'] = write_queue.qsize()
                            break
                        except queue.Full:
                            with self._lock:
                                self._state['backpressure_count'] = int(self._state.get('backpressure_count') or 0) + 1
                            if self._writer_error:
                                raise FrameRecordingError(f'录制写入线程失败: {self._writer_error}') from self._writer_error
                    consecutive_errors = 0
                    if target_fps > 0:
                        remaining = (1.0 / target_fps) - (time.monotonic() - capture_started)
                        if remaining > 0 and stop.wait(remaining):
                            break
                except Exception as exc:
                    consecutive_errors += 1
                    with self._lock:
                        self._state['last_error'] = str(exc)
                    self._publish('capture_error', force=True)
                    if consecutive_errors >= self.MAX_CONSECUTIVE_CAPTURE_ERRORS:
                        raise FrameRecordingError(f'连续截图失败 {consecutive_errors} 次: {exc}') from exc
                    if stop.wait(0.03):
                        break
        except Exception as exc:
            logger.exception('逐帧录制异常')
            final_status = 'error'
            final_error = str(exc)
        finally:
            write_queue = self._write_queue
            writer_thread = self._writer_thread
            if write_queue is not None and writer_thread is not None and writer_thread.is_alive():
                while True:
                    try:
                        write_queue.put(None, timeout=0.1)
                        break
                    except queue.Full:
                        if not writer_thread.is_alive():
                            break
                writer_thread.join(timeout=12.0)
                if writer_thread.is_alive() and not final_error:
                    final_status = 'error'
                    final_error = '录制写入线程未能在超时内完成'
            if self._writer_error and not final_error:
                final_status = 'error'
                final_error = f'录制写入线程失败: {self._writer_error}'
            self._finish(final_status, final_error)

    def request_stop(self, reason: str = 'user') -> dict[str, Any]:
        with self._lock:
            if not self._state['active']:
                return self.get_state()
            self._state['status'] = 'stopping'
            self._state['stop_reason'] = str(reason or 'user')
            stop = self._stop_event
        if stop is not None:
            stop.set()
        self._publish('stopping', force=True)
        return self.get_state()

    def stop(self, reason: str = 'user', timeout: float = 12.0) -> dict[str, Any]:
        self.request_stop(reason)
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.1, float(timeout)))
        return self.get_state()

    def _write_manifest(self, final: bool):
        state = self.get_state()
        output_dir = state.get('output_dir')
        if not output_dir:
            return
        manifest = {
            'schema_version': 2,
            'session_id': state['session_id'],
            'project_path': state['project_path'],
            'target_title': state['target_title'],
            'capture_backend': state['capture_backend'],
            'started_at': state['started_at'],
            'stopped_at': state['stopped_at'],
            'status': state['status'],
            'stop_reason': state['stop_reason'],
            'frame_count': state['frame_count'],
            'capture_count': state['capture_count'],
            'last_capture_at': state['last_capture_at'],
            'last_error': state['last_error'],
            'frames_index': 'frames.jsonl',
            'lossless_png': True,
            'retention_policy': 'never_delete_automatically',
            'recording_mode': state['recording_mode'],
            'target_fps': state['target_fps'],
            'queue_capacity': state['queue_capacity'],
            'backpressure_count': state['backpressure_count'],
            'disk_bytes': state['disk_bytes'],
            'skipped_frame_count': state['skipped_frame_count'],
            'change_threshold': state['change_threshold'],
            'max_session_bytes': state['max_session_bytes'],
            'workspace_size': (
                [state['screen_region'][2] - state['screen_region'][0], state['screen_region'][3] - state['screen_region'][1]]
                if len(state.get('screen_region') or []) == 4 else []
            ),
            'screen_region': state.get('screen_region') or [],
            'event_count': state.get('event_count') or 0,
            'final': bool(final),
        }
        atomic_write_json(os.path.join(output_dir, 'session.json'), manifest)

    def _finish(self, status: str, error: str):
        with self._lock:
            if not self._state.get('output_dir'):
                self._disable_escape()
                return
            if self._finishing or (not self._state['active'] and self._state['status'] in {'stopped', 'error'}):
                return
            self._finishing = True
            self._state['status'] = status
            self._state['stopped_at'] = datetime.now().astimezone().isoformat(timespec='milliseconds')
            if error:
                self._state['last_error'] = error
            self._thread = None
            self._writer_thread = None
            self._stop_event = None
        self._disable_escape()
        try:
            self._write_manifest(final=True)
        except Exception:
            logger.exception('写入逐帧录制会话清单失败')
        finally:
            with self._lock:
                self._state['active'] = False
                self._finishing = False
        self._publish('stopped' if status == 'stopped' else 'error', force=True)


frame_recording_service = FrameRecordingService()
