from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.services.android_stream import ScrcpyVideoSession
from core.vnext.file_runtime_v6 import windows_file_reference
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.platform_runtime_v6 import PlatformRuntimeV6
from core.vnext.runtime import _PLATFORM_RUNTIME_OPCODES
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    DurationValue,
    ProgramDocument,
    ProgramFunction,
    ResultBinding,
    TargetReferenceValue,
)
from core.vnext.runtime import RuntimeFailure, VNextRuntime
from core.vnext.target_runtime import AndroidAdbTargetDriver, WindowsTargetDriver


class _Manager:
    def __init__(self, targets=(), current=None) -> None:
        self.targets = {item['target_id']: dict(item) for item in targets}
        self.current = current

    def resolve_target_definition(self, target_id: str):
        value = self.targets.get(target_id)
        return dict(value) if value is not None else None


class _Process:
    def __init__(self, *, pid: int = 123, exit_code: int | None = None) -> None:
        self.pid = pid
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.exit_code = 0

    def kill(self):
        self.exit_code = -9


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('runtime did not terminate')


def _instruction(
    instruction_id: str,
    function_id: str,
    opcode: str,
    arguments: dict[str, Any],
    *,
    result_slot: str | None = None,
) -> dict[str, Any]:
    return {
        'instruction_id': instruction_id,
        'function_id': function_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': result_slot,
        'platforms': ['windows', 'android_adb', 'no_target'],
        'capabilities': [],
        'source': {},
    }


def _plan(instructions: list[dict[str, Any]], *, targets=()) -> dict[str, Any]:
    return adapt_program_ecir_for_runtime({
        'program_model_version': 1,
        'entry_function_id': 'project.main',
        'targets': list(targets),
        'functions': [{
            'function_id': 'project.main', 'name': '主程序',
            'parameters': [], 'parameter_definitions': [],
            'return_type': 'unit', 'instructions': instructions,
        }],
    })


def test_target_status_and_wait_use_locked_target_reference_and_normal_timeout() -> None:
    target = {
        'target_id': 'target.adb.one', 'type': 'android_adb',
        'name': '模拟器一', 'device_serial': 'emulator-5554',
    }
    now = [0.0]
    calls = [0]

    def probe(_target):
        calls[0] += 1
        online = calls[0] >= 3
        return {'online': online, 'ready': online, 'viewport': [0, 0, 720, 1280] if online else None}

    runtime = PlatformRuntimeV6(
        target_probe=probe,
        monotonic=lambda: now[0],
        sleeper=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    messages: list[str] = []
    result = runtime.execute(
        'target.wait_online', 'official.target.wait_online', {
            'official.target.wait_online.parameter.target': {
                'kind': 'target_ref', 'target_id': 'target.adb.one',
            },
            'official.target.wait_online.parameter.timeout': 1_000,
        }, _Manager([target]), lambda: False, messages.append,
    )
    assert result['target_info.field.online'] is True
    assert result['target_info.field.target_id'] == 'target.adb.one'
    assert result['target_info.field.viewport']['width'] == 720
    assert messages[-1] == '目标已在线：模拟器一'

    timeout = PlatformRuntimeV6(
        target_probe=lambda _target: {'online': False, 'ready': False, 'viewport': None},
        monotonic=lambda: now[0],
        sleeper=lambda seconds: now.__setitem__(0, now[0] + seconds),
    ).execute(
        'target.wait_online', 'official.target.wait_online', {
            'official.target.wait_online.parameter.target': {
                'kind': 'target_ref', 'target_id': 'target.adb.one',
            },
            'official.target.wait_online.parameter.timeout': 0,
        }, _Manager([target]), lambda: False, lambda _message: None,
    )
    assert timeout is None


def test_current_target_status_still_probes_liveness() -> None:
    target = {
        'target_id': 'target.adb.one', 'type': 'android_adb',
        'name': '模拟器一', 'device_serial': 'emulator-5554',
    }
    current = SimpleNamespace(target=target, _size=(720, 1280))
    status = PlatformRuntimeV6(
        target_probe=lambda _target: {
            'online': False, 'ready': False, 'viewport': None,
            'detail': 'device offline',
        },
    ).execute(
        'target.status', 'official.target.read_status', {
            'official.target.read_status.parameter.target': {
                'kind': 'target_ref', 'target_id': 'target.adb.one',
            },
        }, _Manager([target], current=current), lambda: False, lambda _message: None,
    )
    assert status['target_info.field.online'] is False
    assert status['target_info.field.viewport'] is None


def test_target_reference_call_is_locked_into_compiler_target_closure() -> None:
    statement = CallStatement(
        statement_id='statement.wait.target',
        function_id='official.target.wait_online',
        arguments={
            'official.target.wait_online.parameter.target': TargetReferenceValue(
                value_id='value.target', target_id='target.adb.one',
            ),
            'official.target.wait_online.parameter.timeout': DurationValue(
                value_id='value.timeout', milliseconds=500,
            ),
        },
        result_binding=ResultBinding(
            symbol_id='symbol.status', display_name='目标状态',
            value_type='optional<target_info>',
        ),
    )
    document = ProgramDocument(
        document_id='document.wait.target',
        function=ProgramFunction(
            function_id='project.main', display_name='主程序',
            statements=(statement,),
        ),
    )
    target = {
        'target_id': 'target.adb.one', 'type': 'android_adb',
        'name': '模拟器一', 'device_serial': 'emulator-5554',
    }
    compiled = compile_program_document(
        document, official_function_registry_v6,
        target_platform='windows', target_definitions=[target],
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    assert compiled['ecir']['targets'] == [target]
    assert compiled['ecir']['functions'][0]['instructions'][0]['opcode'] == 'target.wait_online'


def test_target_wait_cancellation_and_missing_reference_have_stable_errors() -> None:
    target = {'target_id': 'target.one', 'type': 'windows', 'name': '窗口'}
    runtime = PlatformRuntimeV6(target_probe=lambda _target: {'online': False})
    with pytest.raises(RuntimeFailure) as cancelled:
        runtime.execute(
            'target.wait_online', 'official.target.wait_online', {
                'official.target.wait_online.parameter.target': {
                    'kind': 'target_ref', 'target_id': 'target.one',
                },
                'official.target.wait_online.parameter.timeout': 100,
            }, _Manager([target]), lambda: True, lambda _message: None,
        )
    assert cancelled.value.error_id == 'runtime.cancelled'
    with pytest.raises(RuntimeFailure) as missing:
        runtime.execute(
            'target.status', 'official.target.read_status', {
                'official.target.read_status.parameter.target': {
                    'kind': 'target_ref', 'target_id': 'target.missing',
                },
            }, _Manager([target]), lambda: False, lambda _message: None,
        )
    assert missing.value.error_id == 'target.reference_missing'


def test_windows_application_start_is_argv_only_and_waits_same_process(tmp_path: Path) -> None:
    executable = tmp_path / 'safe-app.exe'
    executable.write_bytes(b'not executed by the fake factory')
    created: list[tuple[list[str], dict[str, Any]]] = []
    process = _Process()

    def factory(argv, **kwargs):
        created.append((list(argv), dict(kwargs)))
        return process

    runtime = PlatformRuntimeV6(process_factory=factory)
    application = {
        'application_ref.field.platform': 'windows',
        'application_ref.field.executable': windows_file_reference(
            str(executable), str(tmp_path), access=('execute',),
        ),
    }
    run = runtime.execute(
        'host.app.start', 'official.application.start', {
            'official.application.start.parameter.application': application,
            'official.application.start.parameter.arguments': ['--profile', '测试'],
        }, _Manager(), lambda: False, lambda _message: None,
    )
    assert created[0][0] == [str(executable), '--profile', '测试']
    assert created[0][1]['shell'] is False
    assert run['application_run_ref.field.process_id'] == 123
    assert runtime.execute(
        'host.app.is_running', 'official.application.is_running', {
            'official.application.is_running.parameter.process': run,
        }, _Manager(), lambda: False, lambda _message: None,
    ) is True

    assert runtime.execute(
        'host.app.wait_exit', 'official.application.wait_exit', {
            'official.application.wait_exit.parameter.process': run,
            'official.application.wait_exit.parameter.timeout': 0,
        }, _Manager(), lambda: False, lambda _message: None,
    ) is None
    with pytest.raises(RuntimeFailure) as cancelled:
        runtime.execute(
            'host.app.wait_exit', 'official.application.wait_exit', {
                'official.application.wait_exit.parameter.process': run,
                'official.application.wait_exit.parameter.timeout': 100,
            }, _Manager(), lambda: True, lambda _message: None,
        )
    assert cancelled.value.error_id == 'runtime.cancelled'
    process.exit_code = 7
    exited = runtime.execute(
        'host.app.wait_exit', 'official.application.wait_exit', {
            'official.application.wait_exit.parameter.process': run,
            'official.application.wait_exit.parameter.timeout': 100,
        }, _Manager(), lambda: False, lambda _message: None,
    )
    assert exited['application_exit_result.field.exit_code'] == 7


def test_windows_application_stop_is_idempotent_and_bound_to_run_reference(tmp_path: Path) -> None:
    executable = tmp_path / 'safe-app.exe'
    executable.write_bytes(b'not executed by the fake factory')
    process = _Process()
    runtime = PlatformRuntimeV6(process_factory=lambda *_args, **_kwargs: process)
    run = runtime.execute(
        'host.app.start', 'official.application.start', {
            'official.application.start.parameter.application': {
                'application_ref.field.platform': 'windows',
                'application_ref.field.executable': windows_file_reference(
                    str(executable), str(tmp_path), access=('execute',),
                ),
            },
            'official.application.start.parameter.arguments': [],
        }, _Manager(), lambda: False, lambda _message: None,
    )
    messages: list[str] = []
    assert runtime.execute(
        'host.app.stop', 'official.application.stop', {
            'official.application.stop.parameter.process': run,
            'official.application.stop.parameter.timeout': 100,
        }, _Manager(), lambda: False, messages.append,
    ) is True
    assert process.exit_code == 0
    assert runtime.execute(
        'host.app.is_running', 'official.application.is_running', {
            'official.application.is_running.parameter.process': run,
        }, _Manager(), lambda: False, lambda _message: None,
    ) is False
    assert runtime.execute(
        'host.app.stop', 'official.application.stop', {
            'official.application.stop.parameter.process': run,
        }, _Manager(), lambda: False, messages.append,
    ) is True
    assert any('无需再次停止' in item for item in messages)


@pytest.mark.parametrize('name', ('cmd.exe', 'PowerShell.EXE', 'script.py', 'task.cmd'))
def test_windows_application_start_rejects_command_and_script_hosts(tmp_path: Path, name: str) -> None:
    executable = tmp_path / name
    executable.write_bytes(b'')
    runtime = PlatformRuntimeV6(process_factory=lambda *_args, **_kwargs: pytest.fail('must not launch'))
    with pytest.raises(RuntimeFailure) as raised:
        runtime.execute(
            'host.app.start', 'official.application.start', {
                'official.application.start.parameter.application': {
                    'application_ref.field.platform': 'windows',
                    'application_ref.field.executable': windows_file_reference(
                        str(executable), str(tmp_path), access=('execute',),
                    ),
                },
                'official.application.start.parameter.arguments': [],
            }, _Manager(), lambda: False, lambda _message: None,
        )
    assert raised.value.error_id == 'application.executable_forbidden'


def test_adb_application_start_accepts_only_typed_package_activity() -> None:
    class Driver:
        platform = 'android_adb'
        target = {'target_id': 'target.adb'}

        def __init__(self) -> None:
            self.calls = []

        def start_application(self, package, activity, arguments, cancelled):
            self.calls.append((package, activity, arguments))
            return {'ok': True, 'message': 'started'}

        def application_running(self, package):
            self.calls.append(('running', package))
            return True

        def stop_application(self, package, cancelled):
            self.calls.append(('stop', package))
            return {'ok': True, 'message': 'stopped'}

    driver = Driver()
    result = PlatformRuntimeV6().execute(
        'host.app.start', 'official.application.start', {
            'official.application.start.parameter.application': {
                'application_ref.field.platform': 'android_adb',
                'application_ref.field.package': 'com.example.game',
                'application_ref.field.activity': '.MainActivity',
            },
            'official.application.start.parameter.arguments': [],
        }, _Manager(current=driver), lambda: False, lambda _message: None,
    )
    assert driver.calls == [('com.example.game', '.MainActivity', [])]
    assert result['application_run_ref.field.target_id'] == 'target.adb'
    runtime = PlatformRuntimeV6()
    run = runtime.execute(
        'host.app.start', 'official.application.start', {
            'official.application.start.parameter.application': {
                'application_ref.field.platform': 'android_adb',
                'application_ref.field.package': 'com.example.game',
                'application_ref.field.activity': '.MainActivity',
            },
            'official.application.start.parameter.arguments': [],
        }, _Manager(current=driver), lambda: False, lambda _message: None,
    )
    assert runtime.execute(
        'host.app.is_running', 'official.application.is_running', {
            'official.application.is_running.parameter.process': run,
        }, _Manager(), lambda: False, lambda _message: None,
    ) is True
    assert runtime.execute(
        'host.app.stop', 'official.application.stop', {
            'official.application.stop.parameter.process': run,
        }, _Manager(), lambda: False, lambda _message: None,
    ) is True
    assert ('running', 'com.example.game') in driver.calls
    assert ('stop', 'com.example.game') in driver.calls

    with pytest.raises(RuntimeFailure) as rejected:
        PlatformRuntimeV6().execute(
            'host.app.start', 'official.application.start', {
                'official.application.start.parameter.application': {
                    'application_ref.field.platform': 'android_adb',
                    'application_ref.field.package': 'com.example.game',
                    'application_ref.field.activity': '.MainActivity',
                },
                'official.application.start.parameter.arguments': ['--es', 'unsafe'],
            }, _Manager(current=driver), lambda: False, lambda _message: None,
        )
    assert rejected.value.error_id == 'application.reference_invalid'


def test_android_activity_adapter_builds_only_fixed_adb_argv() -> None:
    session = object.__new__(ScrcpyVideoSession)
    session.device_id = 'emulator-5554'
    commands: list[tuple[list[str], float]] = []
    def run(command, timeout=10):
        commands.append((list(command), timeout))
        return SimpleNamespace(
            stdout=(
                b'com.example.game/com.example.game.MainActivity\n'
                if 'resolve-activity' in command else b''
            ),
        )

    session._run_adb = run

    result = session.start_activity('com.example.game', '.MainActivity', [])

    assert result['ok'] is True
    assert commands == [
        (['shell', 'am', 'start', '-W', '-n', 'com.example.game/.MainActivity'], 15),
    ]
    assert session.start_activity(
        'com.example.game', '.MainActivity', ['; rm -rf /'],
    )['delivery'] == 'blocked'
    assert len(commands) == 1

    commands.clear()
    assert session.start_activity('com.example.game', '', [])['ok'] is True
    assert commands == [
        ([
            'shell', 'pm', 'resolve-activity', '--brief',
            '-c', 'android.intent.category.LAUNCHER', 'com.example.game',
        ], 10),
        (['shell', 'am', 'start', '-W', '-n', 'com.example.game/com.example.game.MainActivity'], 15),
    ]


def test_android_activity_status_and_stop_build_only_fixed_adb_argv(monkeypatch) -> None:
    session = object.__new__(ScrcpyVideoSession)
    session.device_id = 'emulator-5554'
    running = [True]
    commands: list[list[str]] = []

    def run(command, **_kwargs):
        commands.append(list(command))
        if command[-3:-1] == ['am', 'force-stop']:
            running[0] = False
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        if command[-2] == 'pidof':
            return SimpleNamespace(
                returncode=0 if running[0] else 1,
                stdout=b'1234\n' if running[0] else b'', stderr=b'',
            )
        raise AssertionError(command)

    monkeypatch.setattr('core.services.android_stream.subprocess.run', run)

    assert session.application_running('com.example.game') is True
    result = session.stop_application('com.example.game')
    assert result['ok'] is True
    assert result['verified'] is True
    assert session.application_running('com.example.game') is False
    assert commands == [
        ['adb', '-s', 'emulator-5554', 'shell', 'pidof', 'com.example.game'],
        ['adb', '-s', 'emulator-5554', 'shell', 'am', 'force-stop', 'com.example.game'],
        ['adb', '-s', 'emulator-5554', 'shell', 'pidof', 'com.example.game'],
        ['adb', '-s', 'emulator-5554', 'shell', 'pidof', 'com.example.game'],
    ]
    assert session.stop_application('com.example.game; rm -rf /')['delivery'] == 'blocked'


def _windows_driver() -> WindowsTargetDriver:
    driver = object.__new__(WindowsTargetDriver)
    driver.project_path = ''
    driver.target = {
        'target_id': 'target.windows', 'allow_physical_fallback': True,
        'work_area': {'mode': 'client'},
    }
    driver.hwnd = 101
    driver._box = (10, 20, 810, 620)
    driver._last_message = ''
    driver._window_references = {}
    driver._control_references = {}
    return driver


def test_current_target_window_returns_session_scoped_reference(monkeypatch) -> None:
    import win32gui
    import win32process

    driver = _windows_driver()
    monkeypatch.setattr(win32gui, 'IsWindow', lambda hwnd: hwnd == 101)
    monkeypatch.setattr(win32gui, 'GetClassName', lambda _hwnd: 'Chrome_WidgetWin_0')
    monkeypatch.setattr(win32gui, 'GetWindowText', lambda _hwnd: '超能世界')
    monkeypatch.setattr(win32process, 'GetWindowThreadProcessId', lambda _hwnd: (9, 7))

    reference = driver.execute('window.current', {}, lambda: False)

    assert reference['window_ref.field.handle'] == 101
    assert reference['window_ref.field.process_id'] == 7
    assert reference['window_ref.field.title'] == '超能世界'
    assert reference['window_ref.field.token'] in driver._window_references


def test_window_reference_lifetime_activate_close_and_status(monkeypatch) -> None:
    import win32api
    import win32con
    import win32gui
    import win32process

    driver = _windows_driver()
    monkeypatch.setattr(win32gui, 'IsWindow', lambda hwnd: hwnd == 202)
    monkeypatch.setattr(win32gui, 'GetClassName', lambda _hwnd: 'DemoClass')
    monkeypatch.setattr(win32gui, 'GetWindowText', lambda _hwnd: 'Demo')
    geometry = {
        'outer': (1, 2, 301, 202),
        'client': (0, 0, 284, 192),
    }
    monkeypatch.setattr(win32gui, 'GetWindowRect', lambda _hwnd: geometry['outer'])
    monkeypatch.setattr(win32gui, 'GetClientRect', lambda _hwnd: geometry['client'])
    monkeypatch.setattr(win32gui, 'IsWindowVisible', lambda _hwnd: True)
    monkeypatch.setattr(win32gui, 'IsIconic', lambda _hwnd: False)
    monkeypatch.setattr(win32gui, 'GetWindowPlacement', lambda _hwnd: (0, win32con.SW_SHOWNORMAL, (0, 0), (0, 0), (1, 2, 301, 202)))
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 202)
    operations: list[tuple[str, Any]] = []
    monkeypatch.setattr(win32gui, 'BringWindowToTop', lambda hwnd: operations.append(('top', hwnd)))
    monkeypatch.setattr(win32gui, 'SetForegroundWindow', lambda hwnd: operations.append(('focus', hwnd)))
    def set_window_pos(hwnd, _after, x, y, width, height, flags):
        operations.append(('place', (hwnd, x, y, width, height, flags)))
        left, top, right, bottom = geometry['outer']
        if not flags & win32con.SWP_NOMOVE:
            left, top = x, y
        if not flags & win32con.SWP_NOSIZE:
            right, bottom = left + width, top + height
            geometry['client'] = (0, 0, width - 16, height - 8)
        else:
            right, bottom = left + (right - geometry['outer'][0]), top + (bottom - geometry['outer'][1])
        geometry['outer'] = (left, top, right, bottom)

    monkeypatch.setattr(win32gui, 'SetWindowPos', set_window_pos)
    monkeypatch.setattr(win32gui, 'ShowWindow', lambda hwnd, command: operations.append(('show', (hwnd, command))))
    monkeypatch.setattr(win32gui, 'PostMessage', lambda hwnd, message, _w, _l: operations.append(('post', (hwnd, message))))
    monkeypatch.setattr(win32process, 'GetWindowThreadProcessId', lambda _hwnd: (9, 7))
    monkeypatch.setattr(driver, '_find_window_by_selector', lambda selector: 202)
    monkeypatch.setattr(win32api, 'MonitorFromWindow', lambda _hwnd, _mode: 1)
    monkeypatch.setattr(win32api, 'GetMonitorInfo', lambda _monitor: {'Work': (0, 0, 1920, 1080)})

    reference = driver.execute('window.find', {
        'official.window.find.parameter.selector': {
            'window_selector.field.title': 'Demo',
            'window_selector.field.match_mode': 'exact',
        },
    }, lambda: False)
    assert reference['window_ref.field.process_id'] == 7
    assert driver.execute('window.activate', {
        'official.window.activate.parameter.window': reference,
    }, lambda: False) is True
    status = driver.execute('window.status', {
        'official.window.read_status.parameter.window': reference,
    }, lambda: False)
    assert status['window_status.field.size'] == {'width': 300, 'height': 200}
    assert status['window_status.field.foreground'] is True
    assert status['window_status.field.maximized'] is False
    assert driver.execute('window.move', {
        'official.window.move.parameter.window': reference,
        'official.window.move.parameter.position': {'kind': 'point', 'x': -200, 'y': 40},
    }, lambda: False) is True
    assert driver.execute('window.resize', {
        'official.window.resize.parameter.window': reference,
        'official.window.resize.parameter.size': {'width': 1024, 'height': 768},
    }, lambda: False) is True
    assert geometry['client'] == (0, 0, 1024, 768)
    assert driver.execute('window.ensure_visible', {
        'official.window.ensure_visible.parameter.window': reference,
    }, lambda: False) is True
    assert driver.execute('window.set_display_state', {
        'official.window.set_display_state.parameter.window': reference,
        'official.window.set_display_state.parameter.state': 'maximized',
    }, lambda: False) is True
    assert driver.execute('window.close', {
        'official.window.close.parameter.window': reference,
    }, lambda: False) is True
    assert ('post', (202, win32con.WM_CLOSE)) in operations
    monkeypatch.setattr(win32process, 'GetWindowThreadProcessId', lambda _hwnd: (9, 999))
    with pytest.raises(RuntimeFailure) as reused:
        driver.execute('window.status', {
            'official.window.read_status.parameter.window': reference,
        }, lambda: False)
    assert reused.value.error_id == 'window.reference_invalid'


def test_window_activate_retries_with_attached_foreground_input(monkeypatch) -> None:
    import win32api
    import win32con
    import win32gui
    import win32process

    driver = _windows_driver()
    foreground = {"hwnd": 303}
    attempts: list[int] = []
    attachments: list[tuple[int, int, bool]] = []
    monkeypatch.setattr(win32gui, 'IsWindow', lambda hwnd: hwnd == 202)
    monkeypatch.setattr(win32gui, 'GetClassName', lambda _hwnd: 'DemoClass')
    monkeypatch.setattr(win32gui, 'GetWindowText', lambda _hwnd: 'Demo')
    monkeypatch.setattr(win32gui, 'IsIconic', lambda _hwnd: False)
    monkeypatch.setattr(win32gui, 'ShowWindow', lambda *_args: None)
    monkeypatch.setattr(win32gui, 'BringWindowToTop', lambda *_args: None)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: foreground['hwnd'])
    monkeypatch.setattr(
        win32gui,
        'SetForegroundWindow',
        lambda hwnd: (
            attempts.append(hwnd),
            (_ for _ in ()).throw(RuntimeError('foreground locked'))
            if len(attempts) == 1
            else foreground.__setitem__('hwnd', hwnd),
        )[-1],
    )
    monkeypatch.setattr(win32gui, 'SetWindowPos', lambda *_args: None)
    monkeypatch.setattr(win32api, 'GetCurrentThreadId', lambda: 10)
    monkeypatch.setattr(
        win32process,
        'GetWindowThreadProcessId',
        lambda hwnd: (20 if hwnd == 202 else 30, 1),
    )
    monkeypatch.setattr(
        win32process,
        'AttachThreadInput',
        lambda first, second, attach: attachments.append((first, second, attach)),
    )
    monkeypatch.setattr(driver, '_resolve_window_reference', lambda _reference: 202)

    assert driver.execute(
        'window.activate',
        {'official.window.activate.parameter.window': {'window_ref.field.hwnd': 202}},
        lambda: False,
    ) is True
    assert attempts == [202, 202]
    assert (10, 20, True) in attachments
    assert (10, 30, True) in attachments
    assert attachments[-2:] == [(10, 30, False), (10, 20, False)]


def test_control_reference_is_reused_and_auto_fallback_logs_background_reason(monkeypatch) -> None:
    import core.services.uia_service as uia_service

    driver = _windows_driver()
    info = {
        'name': '确认', 'automation_id': 'ok', 'control_type': 'Button',
        'rect': [100, 120, 180, 160], 'hwnd': 202,
    }
    monkeypatch.setattr(driver, '_find_control', lambda selector, timeout: dict(info))
    reference = driver.execute('control.find', {
        'official.control.find.parameter.selector': {
            'control_selector.field.automation_id': 'ok',
        },
    }, lambda: False)
    assert reference['control_ref.field.target_id'] == 'target.windows'
    monkeypatch.setattr(uia_service, 'perform_uia_action', lambda *_args, **_kwargs: {
        'ok': False, 'message': 'Invoke 与后台消息均不可用',
    })
    reasons: list[str] = []
    monkeypatch.setattr(driver, '_run_physical', lambda reason, _operation, **_kwargs: (
        reasons.append(reason) or {
            'ok': True, 'method': 'physical',
            'message': f'{reason}，已使用物理输入并恢复鼠标位置',
        }
    ))
    assert driver.execute('control.click', {
        'official.control.click.parameter.control': reference,
        'official.control.click.parameter.mode': 'auto',
    }, lambda: False) is True
    assert reasons == ['后台控件操作失败（Invoke 与后台消息均不可用）']
    assert '恢复鼠标位置' in driver.consume_message()
    monkeypatch.setattr(driver, '_find_control', lambda _selector, _timeout: None)
    with pytest.raises(RuntimeFailure) as stale:
        driver.execute('control.read_text', {
            'official.control.read_text.parameter.control': reference,
        }, lambda: False)
    assert stale.value.error_id == 'control.reference_stale'


def test_physical_input_path_always_restores_pointer_and_keeps_foreground(monkeypatch) -> None:
    import sys

    import win32gui

    driver = _windows_driver()
    moves: list[tuple[int, int]] = []
    pointer = [900, 700]

    def move_to(x, y):
        pointer[:] = [int(x), int(y)]
        moves.append((int(x), int(y)))

    fake_pyautogui = SimpleNamespace(
        position=lambda: tuple(pointer),
        moveTo=move_to,
    )
    monkeypatch.setitem(sys.modules, 'pyautogui', fake_pyautogui)
    monkeypatch.setattr(win32gui, 'GetAncestor', lambda hwnd, _kind: hwnd)
    monkeypatch.setattr(win32gui, 'IsWindowVisible', lambda _hwnd: True)
    monkeypatch.setattr(win32gui, 'IsIconic', lambda _hwnd: False)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 101)

    result = driver._run_physical(
        '后台点击失败（目标拒绝）',
        lambda api: (api.moveTo(120, 130) or '点击完成'),
    )

    assert result['method'] == 'physical'
    assert moves == [(120, 130), (900, 700)]
    assert '后台点击失败（目标拒绝）' in result['message']
    assert '恢复鼠标位置' in result['message']


def test_windows_key_fallback_and_pointer_move_expose_real_physical_path(monkeypatch) -> None:
    import win32gui

    driver = _windows_driver()
    monkeypatch.setattr(driver, '_workspace_box', lambda: driver._box)
    monkeypatch.setattr(win32gui, 'PostMessage', lambda *_args: (_ for _ in ()).throw(OSError('blocked')))
    reasons: list[str] = []
    monkeypatch.setattr(driver, '_run_physical', lambda reason, _operation, **_kwargs: (
        reasons.append(reason) or {
            'ok': True, 'method': 'physical',
            'message': f'{reason}，已使用物理输入并恢复鼠标位置',
        }
    ))
    result = driver.execute('input.key', {
        'official.input.key.parameter.key': {'key_chord.field.keys': ['ctrl', 'a']},
        'official.input.key.parameter.action': 'press',
        'official.input.key.parameter.hold': 0,
    }, lambda: False)
    assert result['method'] == 'physical'
    assert reasons[0].startswith('后台按键失败（blocked）')
    pointer = driver.execute('input.move_pointer', {
        'official.input.move_pointer.parameter.position': {'kind': 'point', 'x': 50, 'y': 60},
        'official.input.move_pointer.parameter.duration': 100,
    }, lambda: False)
    assert pointer['method'] == 'physical'
    assert reasons[1] == '已明确执行物理指针移动'


def test_adb_key_uses_scrcpy_target_channel_and_no_pc_keyboard() -> None:
    driver = object.__new__(AndroidAdbTargetDriver)
    driver.target = {'target_id': 'target.adb'}
    driver._last_message = ''

    class Session:
        def __init__(self):
            self.calls = []

        def keyevent(self, keycode, **kwargs):
            self.calls.append((keycode, kwargs))
            return {'ok': True, 'method': 'scrcpy_control', 'message': 'sent'}

    driver.session = Session()
    result = driver.execute('input.key', {
        'official.input.key.parameter.key': {'key_chord.field.keys': ['ctrl', 'a']},
        'official.input.key.parameter.action': 'press',
        'official.input.key.parameter.hold': 20,
    }, lambda: False)
    assert result['method'] == 'scrcpy_control'
    assert driver.session.calls[0][0] == 29
    assert driver.session.calls[0][1]['metastate'] == 0x1000


def test_adb_control_reference_relocates_scales_and_replaces_text() -> None:
    from core.vnext.android_control_v6 import AndroidControlNode, selector_for_node

    node = AndroidControlNode(
        package_name='demo', resource_id='demo:id/name', text='旧文本',
        content_description='', class_name='android.widget.EditText',
        bounds=(270, 468, 810, 702), path=(0, 1), clickable=True,
        editable=True, enabled=True,
    )
    selector = selector_for_node(node, 'target.adb', 'android_uiautomator')

    class Adapter:
        display_size = (1080, 2340)

        def find(self, selected, target_id):
            assert selected == selector
            assert target_id == 'target.adb'
            return node

    class Session:
        def __init__(self):
            self.taps = []
            self.keys = []
            self.inputs = []

        def tap(self, x, y, width, height):
            self.taps.append((x, y, width, height))
            return {'ok': True}

        def keyevent(self, keycode, **kwargs):
            self.keys.append((keycode, kwargs))
            return {'ok': True}

        def inject_text(self, text, **kwargs):
            self.inputs.append((text, kwargs))
            return {'ok': True}

    driver = object.__new__(AndroidAdbTargetDriver)
    driver.target = {'target_id': 'target.adb'}
    driver._last_message = ''
    driver._control_adapter = Adapter()
    driver._control_references = {}
    driver._size = (540, 1170)
    driver.session = Session()

    reference = driver.execute('control.find', {
        'official.control.find.parameter.selector': selector,
    }, lambda: False)
    assert reference['control_ref.field.target_id'] == 'target.adb'
    assert driver.execute('control.read_text', {
        'official.control.read_text.parameter.control': reference,
    }, lambda: False) == '旧文本'
    status = driver.execute('control.read_status', {
        'official.control.read_status.parameter.control': reference,
    }, lambda: False)
    assert status['control_status.field.enabled'] is True
    assert status['control_status.field.editable'] is True
    assert status['control_status.field.current_value'] == '旧文本'
    assert status['control_status.field.rect']['width'] == 540
    assert driver.execute('control.scroll_into_view', {
        'official.control.scroll_into_view.parameter.control': reference,
    }, lambda: False) is True
    assert driver.execute('control.input_text', {
        'official.control.type_text.parameter.control': reference,
        'official.control.type_text.parameter.content': '新文本',
        'official.control.type_text.parameter.mode': 'target',
    }, lambda: False) is True

    assert driver.session.taps == [(270, 292, 540, 1170)]
    assert driver.session.keys == [(29, {'metastate': 0x1000, 'action': 'press'})]
    assert driver.session.inputs == [('新文本', {'paste': True})]


def test_windows_control_status_and_pattern_action_stay_on_uia_path(monkeypatch) -> None:
    import core.services.uia_service as uia_service

    driver = _windows_driver()
    info = {
        'name': '启用高级模式', 'automation_id': 'advanced', 'control_type': 'CheckBox',
        'rect': [100, 120, 260, 160], 'hwnd': 202,
    }
    monkeypatch.setattr(driver, '_find_control', lambda _selector, _timeout: dict(info))
    reference = driver.execute('control.find', {
        'official.control.find.parameter.selector': {
            'control_selector.field.automation_id': 'advanced',
        },
    }, lambda: False)
    actions: list[tuple[str, str]] = []

    def perform(_info, action, text='', **_kwargs):
        actions.append((action, text))
        if action == 'get_status':
            return {
                'ok': True, 'message': '已读取控件状态',
                'value': {
                    'control_status.field.enabled': True,
                    'control_status.field.visible': True,
                    'control_status.field.checked': False,
                    'control_status.field.selected': None,
                    'control_status.field.editable': False,
                    'control_status.field.focusable': True,
                    'control_status.field.focused': False,
                    'control_status.field.current_value': None,
                    'control_status.field.rect': {'kind': 'rect', 'x': 100, 'y': 120, 'width': 160, 'height': 40},
                },
            }
        return {'ok': True, 'message': '完成'}

    monkeypatch.setattr(uia_service, 'perform_uia_action', perform)
    status = driver.execute('control.read_status', {
        'official.control.read_status.parameter.control': reference,
    }, lambda: False)
    assert status['control_status.field.checked'] is False
    assert driver.execute('control.toggle', {
        'official.control.toggle.parameter.control': reference,
    }, lambda: False) is True
    assert driver.execute('control.set_value', {
        'official.control.set_value.parameter.control': reference,
        'official.control.set_value.parameter.value': '新值',
    }, lambda: False) is True
    assert actions == [('get_status', ''), ('toggle', ''), ('set_value', '新值')]


def test_no_target_runtime_dispatches_typed_application_slice(monkeypatch, tmp_path: Path) -> None:
    import core.vnext.platform_runtime_v6 as platform_runtime

    executable = tmp_path / 'safe-app.exe'
    executable.write_bytes(b'')
    process = _Process(exit_code=0)
    monkeypatch.setattr(platform_runtime.subprocess, 'Popen', lambda *_args, **_kwargs: process)
    application = {
        'application_ref.field.platform': 'windows',
        'application_ref.field.executable': windows_file_reference(
            str(executable), str(tmp_path), access=('execute',),
        ),
    }
    instructions = [
        _instruction('start', 'official.application.start', 'host.app.start', {
            'official.application.start.parameter.application': application,
            'official.application.start.parameter.arguments': [],
        }, result_slot='run'),
        _instruction('wait', 'official.application.wait_exit', 'host.app.wait_exit', {
            'official.application.wait_exit.parameter.process': {
                'kind': 'reference', 'scope': 'local', 'symbol_id': 'run',
            },
            'official.application.wait_exit.parameter.timeout': {
                'kind': 'duration', 'milliseconds': 100,
            },
        }, result_slot='exit'),
    ]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_plan(instructions))['execution_id'])
    assert result['status'] == 'completed', result['error']
    assert result['variables']['exit']['application_exit_result.field.exit_code'] == 0
    assert any(item['category'] == 'application' for item in result['events'])


def test_new_platform_contracts_declare_their_structured_runtime_errors() -> None:
    key = official_function_registry_v6.require('official.input.key')
    move = official_function_registry_v6.require('official.input.move_pointer')
    control = official_function_registry_v6.require('official.control.click')
    application = official_function_registry_v6.require('official.application.start')

    assert {
        'target.invalid_key', 'target.invalid_key_action', 'target.invalid_key_hold',
        'target.driver_failed',
    } <= {item.error_id for item in key.errors}
    assert {
        'target.invalid_point', 'target.invalid_duration',
        'target.physical_input_disabled',
    } <= {item.error_id for item in move.errors}
    assert {
        'control.reference_invalid', 'control.reference_stale',
        'control.operation_failed', 'control.physical_input_disabled',
    } <= {item.error_id for item in control.errors}
    assert {
        'application.reference_invalid', 'application.executable_forbidden',
        'application.launch_failed', 'target.reference_missing',
    } <= {item.error_id for item in application.errors}


def test_clipboard_atomic_operations_use_host_adapter_and_preserve_empty_state() -> None:
    values: list[str] = []
    runtime = PlatformRuntimeV6(
        clipboard_reader=lambda: values[-1] if values else None,
        clipboard_writer=values.append,
    )
    assert runtime.execute(
        'clipboard.read_text', 'official.clipboard.read_text', {}, None,
        lambda: False, lambda _message: None,
    ) is None
    assert runtime.execute(
        'clipboard.write_text', 'official.clipboard.write_text', {
            'official.clipboard.write_text.parameter.content': '房间码 215',
        }, None, lambda: False, lambda _message: None,
    ) is None
    assert runtime.execute(
        'clipboard.read_text', 'official.clipboard.read_text', {}, None,
        lambda: False, lambda _message: None,
    ) == '房间码 215'

    read_contract = official_function_registry_v6.require('official.clipboard.read_text')
    write_contract = official_function_registry_v6.require('official.clipboard.write_text')
    assert read_contract.return_type == 'optional<string>'
    assert write_contract.return_type == 'unit'
    assert {'clipboard.unavailable', 'clipboard.read_failed'} <= {item.error_id for item in read_contract.errors}


def test_frame_save_uses_current_or_frozen_pixels_and_crops_atomically(tmp_path: Path, monkeypatch) -> None:
    from PIL import Image

    driver = _windows_driver()
    driver._frame_references = {}
    driver._frame_sequence = 0
    driver.frame_is_bgr = False
    source = Image.new('RGB', (8, 6), (12, 34, 56))
    monkeypatch.setattr(driver, 'capture_frame', lambda: source.copy())
    output = tmp_path / 'crop.png'
    reference = windows_file_reference(str(output), str(tmp_path), access=('write',))

    result = driver.execute('frame.save', {
        'official.frame.save.parameter.file': reference,
        'official.frame.save.parameter.frame': None,
        'official.frame.save.parameter.region': {'kind': 'rect', 'x': 2, 'y': 1, 'width': 4, 'height': 3},
        'official.frame.save.parameter.format': 'png',
        'official.frame.save.parameter.quality': 90,
    }, lambda: False)

    assert result == reference
    with Image.open(output) as saved:
        assert saved.size == (4, 3)
        assert saved.convert('RGB').getpixel((0, 0)) == (12, 34, 56)

    before = output.read_bytes()
    with pytest.raises(RuntimeFailure) as invalid:
        driver.execute('frame.save', {
            'official.frame.save.parameter.file': reference,
            'official.frame.save.parameter.region': {'kind': 'rect', 'x': 7, 'y': 5, 'width': 4, 'height': 3},
            'official.frame.save.parameter.format': 'png',
            'official.frame.save.parameter.quality': 90,
        }, lambda: False)
    assert invalid.value.error_id == 'vision.region_invalid'
    assert output.read_bytes() == before


def test_color_read_and_find_use_rgba_tolerance_region_and_frozen_frame(monkeypatch) -> None:
    from PIL import Image

    driver = _windows_driver()
    driver._frame_references = {}
    driver._frame_sequence = 0
    driver.frame_is_bgr = False
    source = Image.new('RGB', (5, 4), (1, 2, 3))
    source.putpixel((3, 2), (100, 110, 120))
    monkeypatch.setattr(driver, 'capture_frame', lambda: source.copy())
    frozen = driver.execute('target.capture_frame', {}, lambda: False)

    assert driver.execute('color.read', {
        'official.color.read.parameter.position': {'kind': 'point', 'x': 3, 'y': 2},
        'official.color.read.parameter.frame': frozen,
    }, lambda: False) == {
        'color.field.red': 100, 'color.field.green': 110,
        'color.field.blue': 120, 'color.field.alpha': 255,
    }
    assert driver.execute('color.find', {
        'official.color.find.parameter.color': {
            'color.field.red': 102, 'color.field.green': 108,
            'color.field.blue': 121, 'color.field.alpha': 255,
        },
        'official.color.find.parameter.tolerance': 2,
        'official.color.find.parameter.region': {'kind': 'rect', 'x': 2, 'y': 1, 'width': 3, 'height': 3},
        'official.color.find.parameter.frame': frozen,
    }, lambda: False) == {'kind': 'point', 'x': 3, 'y': 2}
    assert driver.execute('color.find', {
        'official.color.find.parameter.color': {
            'color.field.red': 255, 'color.field.green': 255,
            'color.field.blue': 255, 'color.field.alpha': 255,
        },
        'official.color.find.parameter.tolerance': 0,
        'official.color.find.parameter.frame': frozen,
    }, lambda: False) is None

    with pytest.raises(RuntimeFailure) as outside:
        driver.execute('color.read', {
            'official.color.read.parameter.position': {'kind': 'point', 'x': 5, 'y': 0},
            'official.color.read.parameter.frame': frozen,
        }, lambda: False)
    assert outside.value.error_id == 'target.invalid_point'
def test_platform_runtime_opcode_set_is_fully_routed_by_session_runtime() -> None:
    assert _PLATFORM_RUNTIME_OPCODES == PlatformRuntimeV6._OPCODES
