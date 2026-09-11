"""Typed host/target platform operations for format-6 ECIR.

This module is deliberately *not* a command runner.  Windows applications are
launched only from an executable ``file_ref`` carrying ``execute`` access and
Android applications are addressed only by package/activity on the current
ADB target.  No API accepts a shell command string.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .file_runtime_v6 import _validate_reference
from .runtime import RuntimeFailure

_FORBIDDEN_EXECUTABLE_NAMES = frozenset({
    'bash', 'cscript', 'cmd', 'mshta', 'node', 'powershell', 'pwsh', 'py',
    'python', 'pythonw', 'regsvr32', 'rundll32', 'sh', 'wscript',
})
_FORBIDDEN_SCRIPT_SUFFIXES = frozenset({
    '.bat', '.cmd', '.com', '.js', '.jse', '.ps1', '.py', '.pyw', '.sh',
    '.vbs', '.vbe', '.wsf', '.wsh',
})
_PACKAGE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')
_ACTIVITY_RE = re.compile(r'^[A-Za-z0-9_.$]+$')


def _parameter(arguments: dict[str, Any], function_id: str, name: str) -> Any:
    return arguments.get(f'{function_id}.parameter.{name}')


def _cancel(cancelled: Callable[[], bool], operation: str) -> None:
    if cancelled():
        raise RuntimeFailure(f'{operation}已取消', error_id='runtime.cancelled')


def _duration(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeFailure('超时必须是持续时间', error_id='runtime.argument_type')
    if value < 0:
        raise RuntimeFailure('超时不能为负数', error_id='runtime.argument_range')
    return int(value)


def _target_reference(value: Any) -> str:
    if not isinstance(value, dict) or value.get('kind') != 'target_ref':
        raise RuntimeFailure('需要强类型目标引用', error_id='target.reference_invalid')
    target_id = str(value.get('target_id') or '')
    if not target_id:
        raise RuntimeFailure('目标引用缺少稳定 target_id', error_id='target.reference_invalid')
    return target_id


def _application_reference(value: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise RuntimeFailure('需要强类型应用引用', error_id='application.reference_invalid')
    platform = str(value.get('application_ref.field.platform') or '')
    if platform not in {'windows', 'android_adb'}:
        raise RuntimeFailure('应用引用平台必须是 windows 或 android_adb', error_id='application.reference_invalid')
    return platform, value


def _safe_arguments(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeFailure('启动参数必须是文本列表', error_id='application.reference_invalid')
    if len(value) > 128 or sum(len(item) for item in value) > 32_768:
        raise RuntimeFailure('启动参数超过安全上限', error_id='application.reference_invalid')
    if any('\x00' in item for item in value):
        raise RuntimeFailure('启动参数不能包含 NUL', error_id='application.reference_invalid')
    return list(value)


def _windows_executable(reference: Any) -> str:
    try:
        path, _, _ = _validate_reference(reference, 'file_ref', 'execute')
    except RuntimeFailure as exc:
        raise RuntimeFailure(str(exc), error_id='application.reference_invalid') from exc
    suffix = os.path.splitext(path)[1].casefold()
    name = os.path.splitext(os.path.basename(path))[0].casefold()
    if suffix in _FORBIDDEN_SCRIPT_SUFFIXES or name in _FORBIDDEN_EXECUTABLE_NAMES:
        raise RuntimeFailure(
            '应用启动不允许命令解释器、脚本或通用脚本宿主',
            error_id='application.executable_forbidden',
        )
    if suffix != '.exe':
        raise RuntimeFailure(
            'Windows 应用引用首版只接受明确的 .exe 可执行文件',
            error_id='application.executable_forbidden',
        )
    if not os.path.isfile(path):
        raise RuntimeFailure('应用可执行文件不存在', error_id='application.not_found')
    return path


def _windows_target_probe(target: dict[str, Any]) -> dict[str, Any]:
    if os.name != 'nt':
        return {'online': False, 'ready': False, 'viewport': None, 'detail': '当前不是 Windows 宿主'}
    try:
        import win32api
        import win32gui
    except ImportError as exc:
        raise RuntimeFailure('Windows 目标状态驱动缺少 pywin32', error_id='target.driver_failed') from exc
    work_area = dict(target.get('work_area') or {})
    if work_area.get('mode') == 'desktop':
        width = int(win32api.GetSystemMetrics(0))
        height = int(win32api.GetSystemMetrics(1))
        return {
            'online': True, 'ready': width > 0 and height > 0,
            'viewport': [0, 0, width, height], 'detail': '',
        }
    try:
        from .window_binding_v2 import WindowBindingResolutionError, resolve_target_window

        candidate, method = resolve_target_window(target, require_ready=False)
    except WindowBindingResolutionError as exc:
        return {
            'online': exc.error_id != 'target.offline',
            'ready': False,
            'viewport': None,
            'detail': str(exc),
            'error_id': exc.error_id,
        }
    hwnd = int(candidate['hwnd'])
    left, top, right, bottom = (int(item) for item in win32gui.GetWindowRect(hwnd))
    minimized = bool(win32gui.IsIconic(hwnd))
    return {
        'online': True, 'ready': not minimized,
        'viewport': [left, top, max(0, right - left), max(0, bottom - top)],
        'detail': '目标窗口已最小化' if minimized else '',
        'binding_method': method,
    }


def _adb_target_probe(target: dict[str, Any]) -> dict[str, Any]:
    serial = str(target.get('device_serial') or '')
    if not serial or re.search(r'[\s\x00-\x1f]', serial):
        raise RuntimeFailure('ADB 目标缺少有效设备序列号', error_id='target.reference_invalid')
    flags = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)} if os.name == 'nt' else {}
    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'get-state'], capture_output=True, timeout=3,
            check=False, shell=False, **flags,
        )
    except FileNotFoundError as exc:
        raise RuntimeFailure('找不到 ADB 平台工具', error_id='target.driver_failed') from exc
    except subprocess.TimeoutExpired:
        return {'online': False, 'ready': False, 'viewport': None, 'detail': 'ADB 状态查询超时'}
    online = result.returncode == 0 and result.stdout.decode(errors='ignore').strip() == 'device'
    return {
        'online': online, 'ready': online, 'viewport': None,
        'detail': '' if online else (result.stderr or result.stdout).decode(errors='ignore').strip(),
    }


class PlatformRuntimeV6:
    """Execute target registry and typed application lifecycle operations."""

    _OPCODES = frozenset({
        'target.wait_online', 'target.status', 'host.app.start', 'host.app.wait_exit',
        'host.app.is_running', 'host.app.stop',
        'clipboard.read_text', 'clipboard.write_text',
    })

    def __init__(
        self,
        *,
        process_factory: Callable[..., Any] | None = None,
        target_probe: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        clipboard_reader: Callable[[], str | None] | None = None,
        clipboard_writer: Callable[[str], None] | None = None,
    ) -> None:
        self._process_factory = process_factory or subprocess.Popen
        self._target_probe_override = target_probe
        self._monotonic = monotonic
        self._sleep = sleeper
        self._runs: dict[str, dict[str, Any]] = {}
        self._clipboard_reader = clipboard_reader
        self._clipboard_writer = clipboard_writer

    @classmethod
    def supports(cls, opcode: str) -> bool:
        return opcode in cls._OPCODES

    def execute(
        self,
        opcode: str,
        function_id: str,
        arguments: dict[str, Any],
        target_manager: Any,
        cancelled: Callable[[], bool],
        log: Callable[[str], None],
        safe_checkpoint: Callable[[], None] | None = None,
    ) -> Any:
        if not self.supports(opcode):
            raise RuntimeFailure(f'平台运行时不支持：{opcode}', error_id='runtime.operation_unsupported')
        expected = {
            'target.wait_online': 'official.target.wait_online',
            'target.status': 'official.target.read_status',
            'host.app.start': 'official.application.start',
            'host.app.wait_exit': 'official.application.wait_exit',
            'host.app.is_running': 'official.application.is_running',
            'host.app.stop': 'official.application.stop',
            'clipboard.read_text': 'official.clipboard.read_text',
            'clipboard.write_text': 'official.clipboard.write_text',
        }[opcode]
        if function_id != expected:
            raise RuntimeFailure('平台函数稳定 ID 与操作码不匹配', error_id='runtime.contract_mismatch')
        if opcode == 'target.status':
            target = self._resolve_target(
                target_manager, _parameter(arguments, function_id, 'target'), optional=True,
            )
            return self._status(target, target_manager)
        if opcode == 'clipboard.read_text':
            _cancel(cancelled, '读取剪贴板')
            return self._read_clipboard()
        if opcode == 'clipboard.write_text':
            _cancel(cancelled, '写入剪贴板')
            content = _parameter(arguments, function_id, 'content')
            if not isinstance(content, str):
                raise RuntimeFailure('剪贴板内容必须是文本', error_id='runtime.argument_type')
            self._write_clipboard(content)
            return None
        if opcode == 'target.wait_online':
            target = self._resolve_target(
                target_manager, _parameter(arguments, function_id, 'target'), optional=False,
            )
            timeout_ms = _duration(_parameter(arguments, function_id, 'timeout'), default=60_000)
            deadline = self._monotonic() + timeout_ms / 1000.0
            while True:
                if safe_checkpoint is not None:
                    safe_checkpoint()
                _cancel(cancelled, '等待目标在线')
                status = self._status(target, target_manager)
                if status['target_info.field.online']:
                    log(f'目标已在线：{target.get("name") or target.get("target_id")}')
                    return status
                if self._monotonic() >= deadline:
                    log(f'等待目标在线到期：{target.get("name") or target.get("target_id")}')
                    return None
                self._sleep(min(0.1, max(0.0, deadline - self._monotonic())))
        if opcode == 'host.app.start':
            return self._start_application(function_id, arguments, target_manager, cancelled, log)
        if opcode == 'host.app.is_running':
            _cancel(cancelled, '读取应用状态')
            return self._application_is_running(function_id, arguments)
        if opcode == 'host.app.stop':
            return self._stop_application(
                function_id, arguments, cancelled, log, safe_checkpoint,
            )
        return self._wait_application(
            function_id, arguments, cancelled, log, safe_checkpoint,
        )

    def _read_clipboard(self) -> str | None:
        if self._clipboard_reader is not None:
            return self._clipboard_reader()
        if os.name != 'nt':
            raise RuntimeFailure('当前宿主没有 Windows 剪贴板', error_id='clipboard.unavailable')
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
        except Exception as exc:
            raise RuntimeFailure('剪贴板正被其他程序占用', error_id='clipboard.unavailable', transient=True) from exc
        try:
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return None
            return str(win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT))
        except Exception as exc:
            raise RuntimeFailure('无法读取剪贴板文本', error_id='clipboard.read_failed', transient=True) from exc
        finally:
            win32clipboard.CloseClipboard()

    def _write_clipboard(self, content: str) -> None:
        if self._clipboard_writer is not None:
            self._clipboard_writer(content)
            return
        if os.name != 'nt':
            raise RuntimeFailure('当前宿主没有 Windows 剪贴板', error_id='clipboard.unavailable')
        try:
            import win32clipboard
            import win32con
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, content)
            finally:
                win32clipboard.CloseClipboard()
        except RuntimeFailure:
            raise
        except Exception as exc:
            raise RuntimeFailure('写入剪贴板失败', error_id='clipboard.write_failed', transient=True) from exc

    @staticmethod
    def _resolve_target(target_manager: Any, reference: Any, *, optional: bool) -> dict[str, Any] | None:
        if reference is None and optional:
            current = getattr(target_manager, 'current', None)
            return dict(getattr(current, 'target', {}) or {}) or None
        target_id = _target_reference(reference)
        resolver = getattr(target_manager, 'resolve_target_definition', None)
        target = resolver(target_id) if callable(resolver) else None
        if target is None:
            raise RuntimeFailure(f'目标引用已失效：{target_id}', error_id='target.reference_missing')
        return dict(target)

    def _status(self, target: dict[str, Any] | None, target_manager: Any) -> dict[str, Any]:
        if target is None:
            return {
                'target_info.field.target_id': '',
                'target_info.field.name': '无操作目标',
                'target_info.field.kind': 'no_target',
                'target_info.field.online': True,
                'target_info.field.ready': True,
                'target_info.field.viewport': None,
                'target_info.field.space_version': 'no_target',
                'target_info.field.capabilities': [],
                'target_info.field.detail': '',
            }
        target_id = str(target.get('target_id') or '')
        current = getattr(target_manager, 'current', None)
        current_target = dict(getattr(current, 'target', {}) or {}) if current is not None else {}
        if self._target_probe_override is not None:
            probe = dict(self._target_probe_override(target))
        elif target.get('type') == 'windows':
            probe = _windows_target_probe(target)
        elif target.get('type') == 'android_adb':
            probe = _adb_target_probe(target)
        elif target.get('type') == 'android_local':
            probe = {
                'online': False, 'ready': False, 'viewport': None,
                'detail': 'Windows Runtime 不能探测 Android 本机目标',
            }
        else:
            raise RuntimeFailure('目标类型无效', error_id='target.reference_invalid')
        if current_target.get('target_id') == target_id and probe.get('online'):
            if getattr(current, '_box', None):
                left, top, right, bottom = current._box
                probe['viewport'] = [
                    int(left), int(top), int(right - left), int(bottom - top),
                ]
            elif getattr(current, '_size', None) and tuple(current._size) != (0, 0):
                probe['viewport'] = [0, 0, int(current._size[0]), int(current._size[1])]
        viewport = probe.get('viewport')
        rect = None if viewport is None else {
            'kind': 'rect', 'x': int(viewport[0]), 'y': int(viewport[1]),
            'width': int(viewport[2]), 'height': int(viewport[3]),
        }
        kind = str(target.get('type') or '')
        capabilities = {
            'windows': ['target.capture_frame', 'target.input', 'window.uia', 'window.manage', 'control.semantic', 'input.key', 'pointer.move', 'application.launch', 'application.lifecycle'],
            'android_adb': ['target.capture_frame', 'target.input', 'control.semantic', 'input.key', 'application.launch', 'application.lifecycle'],
            'android_local': [],
        }.get(kind, [])
        size = 'unknown' if rect is None else f'{rect["width"]}x{rect["height"]}'
        return {
            'target_info.field.target_id': target_id,
            'target_info.field.name': str(target.get('name') or target_id),
            'target_info.field.kind': kind,
            'target_info.field.online': bool(probe.get('online')),
            'target_info.field.ready': bool(probe.get('ready')),
            'target_info.field.viewport': rect,
            'target_info.field.space_version': f'{target_id}:{size}',
            'target_info.field.capabilities': capabilities,
            'target_info.field.detail': str(probe.get('detail') or ''),
        }

    def _start_application(
        self,
        function_id: str,
        arguments: dict[str, Any],
        target_manager: Any,
        cancelled: Callable[[], bool],
        log: Callable[[str], None],
    ) -> dict[str, Any]:
        _cancel(cancelled, '启动应用')
        platform, reference = _application_reference(
            _parameter(arguments, function_id, 'application'),
        )
        extra = _safe_arguments(_parameter(arguments, function_id, 'arguments'))
        run_id = f'application_run.{uuid.uuid4().hex}'
        started_at = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        if platform == 'windows':
            executable = _windows_executable(reference.get('application_ref.field.executable'))
            try:
                process = self._process_factory(
                    [executable, *extra], cwd=os.path.dirname(executable) or None,
                    shell=False, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError as exc:
                raise RuntimeFailure('应用可执行文件不存在', error_id='application.not_found') from exc
            except OSError as exc:
                raise RuntimeFailure(f'应用启动失败：{exc}', error_id='application.launch_failed', transient=True) from exc
            process_id = int(getattr(process, 'pid', 0) or 0)
            self._runs[run_id] = {
                'platform': platform, 'process': process, 'driver': None,
                'application': reference, 'result': None,
            }
            log(f'已启动 Windows 应用：{os.path.basename(executable)}（PID {process_id or "未知"}）')
            target_id = ''
        else:
            package = str(reference.get('application_ref.field.package') or '')
            activity = str(reference.get('application_ref.field.activity') or '')
            if not _PACKAGE_RE.fullmatch(package) or (activity and not _ACTIVITY_RE.fullmatch(activity)):
                raise RuntimeFailure('Android 包名或 Activity 格式无效', error_id='application.reference_invalid')
            if extra:
                raise RuntimeFailure(
                    'ADB 应用启动首版只接受类型化包名和 Activity，不接受自由启动参数',
                    error_id='application.reference_invalid',
                )
            driver = getattr(target_manager, 'current', None)
            if driver is None or str(getattr(driver, 'platform', '')) != 'android_adb':
                raise RuntimeFailure(
                    'Android 应用只能在当前 ADB 目标中启动',
                    error_id='target.reference_missing',
                )
            launcher = getattr(driver, 'start_application', None)
            if not callable(launcher):
                raise RuntimeFailure('当前 ADB 驱动不支持应用启动', error_id='application.launch_failed')
            result = launcher(package, activity, extra, cancelled)
            if not result.get('ok'):
                raise RuntimeFailure(str(result.get('message') or 'Android 应用启动失败'), error_id='application.launch_failed', transient=True)
            target_id = str(getattr(driver, 'target', {}).get('target_id') or '')
            process_id = 0
            self._runs[run_id] = {
                'platform': platform, 'process': None, 'driver': driver,
                'application': reference, 'result': None,
            }
            log(str(result.get('message') or f'已启动 Android 应用：{package}'))
        return {
            'application_run_ref.field.run_id': run_id,
            'application_run_ref.field.platform': platform,
            'application_run_ref.field.application': reference,
            'application_run_ref.field.process_id': process_id,
            'application_run_ref.field.target_id': target_id,
            'application_run_ref.field.started_at': started_at,
        }

    def _application_entry(
        self, function_id: str, arguments: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        reference = _parameter(arguments, function_id, 'process')
        if not isinstance(reference, dict):
            raise RuntimeFailure('需要强类型应用运行引用', error_id='application.reference_invalid')
        run_id = str(reference.get('application_run_ref.field.run_id') or '')
        entry = self._runs.get(run_id)
        if entry is None:
            raise RuntimeFailure('应用运行引用不属于当前运行会话', error_id='application.reference_invalid')
        return run_id, entry

    def _application_is_running(
        self, function_id: str, arguments: dict[str, Any],
    ) -> bool:
        _, entry = self._application_entry(function_id, arguments)
        if entry['platform'] == 'windows':
            process = entry.get('process')
            return process is not None and process.poll() is None
        driver = entry.get('driver')
        probe = getattr(driver, 'application_running', None)
        if not callable(probe):
            raise RuntimeFailure(
                '当前 ADB 驱动不支持应用状态读取',
                error_id='application.lifecycle_unavailable',
            )
        package = str((entry.get('application') or {}).get('application_ref.field.package') or '')
        return bool(probe(package))

    def _stop_application(
        self,
        function_id: str,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
        log: Callable[[str], None],
        safe_checkpoint: Callable[[], None] | None,
    ) -> bool:
        run_id, entry = self._application_entry(function_id, arguments)
        timeout_ms = _duration(_parameter(arguments, function_id, 'timeout'), default=5_000)
        _cancel(cancelled, '停止应用')
        if entry['platform'] == 'android_adb':
            driver = entry.get('driver')
            stopper = getattr(driver, 'stop_application', None)
            if not callable(stopper):
                raise RuntimeFailure(
                    '当前 ADB 驱动不支持停止应用',
                    error_id='application.lifecycle_unavailable',
                )
            package = str((entry.get('application') or {}).get('application_ref.field.package') or '')
            result = stopper(package, cancelled)
            if not result.get('ok'):
                raise RuntimeFailure(
                    str(result.get('message') or 'Android 应用停止失败'),
                    error_id='application.stop_failed', transient=True,
                )
            log(str(result.get('message') or f'已停止 Android 应用：{package}'))
            return True

        process = entry.get('process')
        if process is None:
            raise RuntimeFailure('应用运行引用无有效进程', error_id='application.reference_invalid')
        if process.poll() is not None:
            log('应用已经退出，无需再次停止')
            return True
        try:
            process.terminate()
        except OSError as exc:
            raise RuntimeFailure('停止 Windows 应用失败', error_id='application.stop_failed', transient=True) from exc
        deadline = self._monotonic() + timeout_ms / 1000.0
        while process.poll() is None and self._monotonic() < deadline:
            if safe_checkpoint is not None:
                safe_checkpoint()
            _cancel(cancelled, '停止应用')
            self._sleep(min(0.05, max(0.0, deadline - self._monotonic())))
        if process.poll() is None:
            try:
                process.kill()
            except OSError as exc:
                raise RuntimeFailure('强制停止 Windows 应用失败', error_id='application.stop_failed', transient=True) from exc
            if process.poll() is None:
                raise RuntimeFailure('Windows 应用未能停止', error_id='application.stop_failed', transient=True)
        log(f'已停止 Windows 应用（运行 ID {run_id}）')
        return True

    def _wait_application(
        self,
        function_id: str,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
        log: Callable[[str], None],
        safe_checkpoint: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        run_id, entry = self._application_entry(function_id, arguments)
        if entry['platform'] != 'windows' or entry['process'] is None:
            raise RuntimeFailure('当前应用引用不支持可靠退出观察', error_id='application.lifecycle_unavailable')
        timeout_ms = _duration(_parameter(arguments, function_id, 'timeout'), default=60_000)
        deadline = self._monotonic() + timeout_ms / 1000.0
        while True:
            if safe_checkpoint is not None:
                safe_checkpoint()
            _cancel(cancelled, '等待应用退出')
            result = entry.get('result')
            if result is not None:
                return dict(result)
            exit_code = entry['process'].poll()
            if exit_code is not None:
                result = {
                    'application_exit_result.field.run_id': run_id,
                    'application_exit_result.field.exit_code': int(exit_code),
                    'application_exit_result.field.finished_at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                }
                entry['result'] = result
                log(f'应用已退出：代码 {int(exit_code)}')
                return dict(result)
            if self._monotonic() >= deadline:
                log('等待应用退出到期，应用仍在运行')
                return None
            self._sleep(min(0.05, max(0.0, deadline - self._monotonic())))


__all__ = ['PlatformRuntimeV6']
