from __future__ import annotations

import time
from typing import Any

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_contracts import LOG_OUTPUT_CONTENT_PARAMETER_ID, LOG_OUTPUT_FUNCTION_ID
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    ProgramDocument,
    ProgramFunction,
    StringValue,
    TargetReferenceValue,
    TargetScopeStatement,
)
from core.vnext.runtime import RuntimeFailure, VNextRuntime


class FakeTargetDriver:
    platform = 'windows'

    def __init__(self, target: dict[str, Any], events: list[str], *, fail_frame: bool = False) -> None:
        self.target = dict(target)
        self.events = events
        self.fail_frame = fail_frame
        self.closed = False

    def capture_frame(self) -> object:
        self.events.append(f'frame:{self.target["target_id"]}')
        if self.fail_frame:
            raise RuntimeFailure('first frame failed', error_id='target.first_frame_failed')
        return object()

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode in {'probe.target', 'probe.fail', 'probe.block'}

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled) -> str:
        target_id = str(self.target['target_id'])
        self.events.append(f'execute:{target_id}:{opcode}')
        if opcode == 'probe.fail':
            raise RuntimeFailure('probe failed', error_id='probe.failed')
        if opcode == 'probe.block':
            while not cancelled():
                time.sleep(0.005)
            raise RuntimeFailure('cancelled', error_id='runtime.cancelled')
        return target_id

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.events.append(f'close:{self.target["target_id"]}')


def _instruction(instruction_id: str, opcode: str, arguments=None, result_slot=None):
    return {
        'instruction_id': instruction_id,
        'opcode': opcode,
        'arguments': arguments or {},
        'result_slot': result_slot,
        'platforms': ['windows', 'android_adb'],
    }


def _scope(instruction_id: str, target_id: str, body: list[dict[str, Any]]):
    return _instruction(instruction_id, 'control.target_scope', {
        'target': {'kind': 'target_ref', 'target_id': target_id},
        'body': body,
        'restore_logical_target': True,
    })


def _plan(instructions: list[dict[str, Any]], targets: list[dict[str, Any]]):
    return {
        'program_model_version': 1,
        'entry_function_id': 'project.main',
        'functions': [{
            'function_id': 'project.main', 'name': 'main',
            'parameters': [], 'return_type': 'unit', 'instructions': instructions,
        }],
        'project_variables': [],
        'supported_platforms': ['windows'],
        'target_platform': 'windows',
        'targets': targets,
    }


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('runtime did not terminate')


def test_windows_adb_nested_scope_restores_and_releases_drivers() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    initial = FakeTargetDriver(windows, events)

    def factory(_project_path: str, target: dict[str, Any]):
        driver = FakeTargetDriver(target, events)
        driver.platform = 'android_adb' if target['type'] == 'android_adb' else 'windows'
        return driver

    instructions = [
        _scope('scope.adb', 'target.adb', [
            _instruction('probe.adb', 'probe.target', result_slot='result.adb'),
            _scope('scope.windows', 'target.windows', [
                _instruction('probe.windows.inner', 'probe.target', result_slot='result.windows.inner'),
            ]),
            _instruction('probe.adb.restored', 'probe.target', result_slot='result.adb.restored'),
        ]),
        _instruction('probe.windows.outer', 'probe.target', result_slot='result.windows.outer'),
    ]
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _plan(instructions, [windows, adb]), initial,
        target=windows, target_driver_factory=factory,
    )['execution_id']
    snapshot = _terminal(runtime, execution_id)
    assert snapshot['status'] == 'completed', snapshot['error']
    assert snapshot['variables'] == {
        'result.adb': 'target.adb',
        'result.windows.inner': 'target.windows',
        'result.adb.restored': 'target.adb',
        'result.windows.outer': 'target.windows',
    }
    assert events.count('frame:target.adb') == 1
    assert events.count('close:target.adb') == 1
    assert events.count('close:target.windows') == 1


def test_scope_first_frame_failure_keeps_previous_target_and_releases_candidate() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    candidate: list[FakeTargetDriver] = []

    def factory(_project_path: str, target: dict[str, Any]):
        driver = FakeTargetDriver(target, events, fail_frame=True)
        candidate.append(driver)
        return driver

    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(
        _plan([_scope('scope.adb', 'target.adb', [])], [windows, adb]),
        FakeTargetDriver(windows, events), target=windows, target_driver_factory=factory,
    )['execution_id'])
    assert snapshot['status'] == 'failed'
    assert snapshot['error_id'] == 'target.first_frame_failed'
    assert candidate[0].closed is True
    deadline = time.monotonic() + 1
    while 'close:target.windows' not in events and time.monotonic() < deadline:
        time.sleep(0.005)
    assert events.count('close:target.windows') == 1


def test_scope_cancel_closes_scoped_and_initial_drivers() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    runtime = VNextRuntime(persist_event_log=False)
    started = runtime.start(
        _plan([_scope('scope.adb', 'target.adb', [
            _instruction('probe.block', 'probe.block'),
        ])], [windows, adb]),
        FakeTargetDriver(windows, events), target=windows,
        target_driver_factory=lambda _path, target: FakeTargetDriver(target, events),
    )
    deadline = time.monotonic() + 2
    while 'execute:target.adb:probe.block' not in events and time.monotonic() < deadline:
        time.sleep(0.005)
    runtime.cancel(started['execution_id'])
    snapshot = _terminal(runtime, started['execution_id'])
    assert snapshot['status'] == 'cancelled'
    assert events.count('close:target.adb') == 1
    assert events.count('close:target.windows') == 1


def test_scope_failure_restores_previous_target_before_outer_catch() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    tried = _instruction('try.scope', 'control.try', {
        'body': [_scope('scope.adb', 'target.adb', [
            _instruction('probe.fail', 'probe.fail'),
        ])],
        'retry_policy': None,
        'catches': [{
            'catch_id': 'catch.probe', 'error_ids': ['probe.failed'],
            'error_slot': 'caught.error',
            'body': [_instruction(
                'probe.after.catch', 'probe.target', result_slot='result.after.catch',
            )],
        }],
        'finally': [],
    })
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(
        _plan([tried], [windows, adb]), FakeTargetDriver(windows, events),
        target=windows,
        target_driver_factory=lambda _path, target: FakeTargetDriver(target, events),
    )['execution_id'])
    assert snapshot['status'] == 'completed', snapshot['error']
    assert snapshot['variables']['result.after.catch'] == 'target.windows'
    assert events.index('close:target.adb') < events.index(
        'execute:target.windows:probe.target',
    )


def test_stale_runtime_target_reference_fails_without_executing_body() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(
        _plan([_scope('scope.missing', 'target.missing', [
            _instruction('probe.must.not.run', 'probe.target'),
        ])], [windows]),
        FakeTargetDriver(windows, events), target=windows,
    )['execution_id'])
    assert snapshot['status'] == 'failed'
    assert snapshot['error_id'] == 'target.reference_missing'
    assert not any(item.startswith('execute:') for item in events)


def test_runtime_creates_default_target_from_compiled_closure() -> None:
    events: list[str] = []
    windows = {'target_id': 'target.windows', 'type': 'windows', 'name': 'Windows'}
    plan = _plan([
        _instruction('probe.default', 'probe.target', result_slot='result.default'),
    ], [windows])
    plan['default_target_id'] = 'target.windows'
    runtime = VNextRuntime(persist_event_log=False)
    snapshot = _terminal(runtime, runtime.start(
        plan,
        target_driver_factory=lambda _path, target: FakeTargetDriver(target, events),
    )['execution_id'])
    assert snapshot['status'] == 'completed', snapshot['error']
    assert snapshot['variables']['result.default'] == 'target.windows'
    assert events == [
        'frame:target.windows',
        'execute:target.windows:probe.target',
        'close:target.windows',
    ]


def test_same_scoped_target_is_not_operated_by_two_sessions_concurrently() -> None:
    events: list[str] = []
    windows_one = {'target_id': 'target.windows.one', 'type': 'windows', 'name': 'Windows 1'}
    windows_two = {'target_id': 'target.windows.two', 'type': 'windows', 'name': 'Windows 2'}
    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    runtime = VNextRuntime(persist_event_log=False)

    def factory(_path: str, target: dict[str, Any]) -> FakeTargetDriver:
        return FakeTargetDriver(target, events)

    first = runtime.start(
        _plan([_scope('scope.adb.one', 'target.adb', [
            _instruction('probe.block.one', 'probe.block'),
        ])], [windows_one, adb]),
        FakeTargetDriver(windows_one, events), target=windows_one,
        target_driver_factory=factory,
    )
    deadline = time.monotonic() + 2
    while 'execute:target.adb:probe.block' not in events and time.monotonic() < deadline:
        time.sleep(0.005)
    second = runtime.start(
        _plan([_scope('scope.adb.two', 'target.adb', [])], [windows_two, adb]),
        FakeTargetDriver(windows_two, events), target=windows_two,
        target_driver_factory=factory,
    )
    second_snapshot = _terminal(runtime, second['execution_id'])
    assert second_snapshot['status'] == 'failed'
    assert second_snapshot['error_id'] == 'target.busy'
    runtime.cancel(first['execution_id'])
    assert _terminal(runtime, first['execution_id'])['status'] == 'cancelled'


def test_compiler_embeds_deterministic_target_closure_and_blocks_stale_reference() -> None:
    document = ProgramDocument(
        document_id='document.target.scope',
        function=ProgramFunction(
            function_id='project.target.scope', display_name='目标作用域',
            statements=(TargetScopeStatement(
                statement_id='statement.scope',
                target=TargetReferenceValue(value_id='value.target', target_id='target.adb'),
                body=(CallStatement(
                    statement_id='statement.log', function_id=LOG_OUTPUT_FUNCTION_ID,
                    arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: StringValue(
                        value_id='value.log', value='ADB',
                    )},
                ),),
            ),),
        ),
    )
    missing = compile_program_document(
        document, official_function_registry_v6, target_platform='windows',
    )
    assert missing['valid'] is False
    assert any(item['code'] == 'PGM-TARGET-001' for item in missing['diagnostics'])

    adb = {'target_id': 'target.adb', 'type': 'android_adb', 'name': 'ADB', 'device_serial': 'emulator-1'}
    compiled = compile_program_document(
        document, official_function_registry_v6, target_platform='windows',
        target_definitions=[adb],
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    assert compiled['ecir']['targets'] == [adb]
    adapted = adapt_program_ecir_for_runtime(compiled['ecir'])
    scope = adapted['functions'][0]['instructions'][0]
    assert scope['opcode'] == 'control.target_scope'
    assert scope['arguments']['target']['target_id'] == 'target.adb'

    android_local = compile_program_document(
        document, official_function_registry_v6, target_platform='windows',
        target_definitions=[{
            'target_id': 'target.adb', 'type': 'android_local', 'name': '当前手机',
        }],
    )
    assert android_local['valid'] is False
    assert any(item['code'] == 'PGM-TARGET-003' for item in android_local['diagnostics'])
