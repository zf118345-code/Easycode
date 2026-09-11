from __future__ import annotations

import time
from typing import Any

import numpy as np
import pytest

from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.runtime import RuntimeFailure, VNextRuntime
from core.vnext.target_runtime import TargetDriver, WindowsTargetDriver


class _FakeTargetDriver(TargetDriver):
    def __init__(self, platform: str) -> None:
        self.platform = platform
        self.project_path = ''
        self.target = {'target_id': f'target.{platform}'}
        self._last_message = ''
        self._page_context_depth = 0
        self._navigator = None
        self._frame_references = {}
        self._ocr_analysis_cache = {}
        self._prepared_asset_cache = {}
        self._frame_sequence = 0
        self.actions: list[tuple[str, Any]] = []
        self.last_text_arguments: dict[str, Any] = {}

    def capture_frame(self):
        self.actions.append(('capture', None))
        return np.zeros((80, 100, 3), dtype=np.uint8)

    def tap_point(self, x: int, y: int, button: str) -> dict[str, Any]:
        self.actions.append(('click', (x, y, button)))
        return {'ok': True, 'message': f'click:{x},{y}:{button}'}

    def input_text(self, arguments: dict[str, Any], cancelled) -> dict[str, Any]:
        self.last_text_arguments = dict(arguments)
        self.actions.append(('text', arguments['内容']))
        return {'ok': True, 'message': 'text'}

    def scroll(self, arguments: dict[str, Any], cancelled) -> dict[str, Any]:
        self.actions.append(('scroll', arguments))
        return {'ok': True, 'message': 'scroll'}

    def drag_path(self, arguments: dict[str, Any], cancelled) -> dict[str, Any]:
        self.actions.append(('drag', arguments))
        return {'ok': True, 'message': 'drag'}

    def _prepared(self, arguments: dict[str, Any]):
        self.actions.append(('asset', arguments['图片']['asset_id']))
        return ('prepared',)

    def _match_frame_once(self, source_frame, variants, threshold, region=None):
        self.actions.append(('find', (source_frame, threshold, region)))
        return {
            '已找到': True,
            '置信度': 0.93,
            '中心': [20, 30],
            '区域': [15, 25, 10, 10],
        }

    def _v6_find_matches(self, arguments, *, owner_function_id, limit):
        image = arguments[f'{owner_function_id}.parameter.image']
        self.actions.append(('asset', image['asset_id']))
        threshold = self._v6_similarity(
            arguments.get(f'{owner_function_id}.parameter.similarity', 0.85)
        )
        region = self._v6_rect(arguments.get(f'{owner_function_id}.parameter.region'))
        _frame, reference, _frame_id = self._frame_for_v6_call(arguments, owner_function_id)
        self.actions.append(('find', ('frame-pixels', threshold, region)))
        return [{
            'image_match.field.center': {'kind': 'point', 'x': 20, 'y': 30},
            'image_match.field.region': {
                'kind': 'rect', 'x': 15, 'y': 25, 'width': 10, 'height': 10,
            },
            'image_match.field.similarity': 0.93,
            'image_match.field.source_asset': {'kind': 'asset_ref', 'asset_id': image['asset_id']},
            'image_match.field.source_frame': reference,
            'image_match.field.source_target': reference['frame_ref.field.source_target'],
            'image_match.field.space_version': reference['frame_ref.field.space_version'],
        }]


def _instruction(
    instruction_id: str,
    function_id: str,
    opcode: str,
    arguments: dict[str, Any],
    *,
    result_slot: str | None = None,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'instruction_id': instruction_id,
        'function_id': function_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': result_slot,
        'source': {},
        'platforms': platforms or ['windows', 'android_adb'],
        'capabilities': ['target.input'],
        'callee_function_id': None,
    }


def _plan(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    return adapt_program_ecir_for_runtime({
        'program_model_version': 1,
        'entry_function_id': 'project.main',
        'functions': [{
            'function_id': 'project.main',
            'name': '主程序',
            'parameters': [],
            'parameter_definitions': [],
            'return_type': 'null',
            'instructions': instructions,
        }],
    })


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = runtime.snapshot(execution_id)
        if result['status'] in {'completed', 'failed', 'cancelled'}:
            return result
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


@pytest.mark.parametrize('platform', ('windows', 'android_adb'))
def test_stable_input_contracts_reach_windows_and_adb_target_driver(platform: str) -> None:
    instructions = [
        _instruction('click', 'official.input.click', 'input.click', {
            'official.input.click.parameter.position': {'kind': 'point', 'x': 10, 'y': 11},
            'official.input.click.parameter.button': 'primary',
            'official.input.click.parameter.count': 2,
            'official.input.click.parameter.hold': {'kind': 'duration', 'milliseconds': 0},
            'official.input.click.parameter.interval': {'kind': 'duration', 'milliseconds': 0},
        }),
        _instruction('text', 'official.input.type_text', 'input.text', {
            'official.input.type_text.parameter.content': '你好',
            'official.input.type_text.parameter.mode': 'auto',
        }),
        _instruction('scroll', 'official.input.scroll', 'input.scroll', {
            'official.input.scroll.parameter.direction': 'down',
            'official.input.scroll.parameter.mode': 'auto',
            'official.input.scroll.parameter.distance': 0.6,
            'official.input.scroll.parameter.start': {'kind': 'point', 'x': 12, 'y': 13},
            'official.input.scroll.parameter.duration': {'kind': 'duration', 'milliseconds': 350},
            'official.input.scroll.parameter.hold': {'kind': 'duration', 'milliseconds': 80},
        }),
        _instruction('drag', 'official.input.drag', 'input.drag', {
            'official.input.drag.parameter.path': {
                'kind': 'path',
                'points': [{'x': 1, 'y': 2}, {'x': 3, 'y': 4}],
            },
            'official.input.drag.parameter.duration': {'kind': 'duration', 'milliseconds': 600},
            'official.input.drag.parameter.easing': 'linear',
        }),
    ]
    driver = _FakeTargetDriver(platform)
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_plan(instructions), driver=driver)['execution_id'])
    assert result['status'] == 'completed', result['error']
    assert driver.actions[:3] == [
        ('click', (10, 11, '左键')),
        ('click', (10, 11, '左键')),
        ('text', '你好'),
    ]
    assert [item[0] for item in driver.actions] == [
        'click', 'click', 'text', 'scroll', 'drag',
    ]
    assert driver.last_text_arguments == {'内容': '你好', '模式': 'auto'}
    assert driver.actions[-1] == ('drag', {
        '路径': [
            {'point': [1, 2], 'move_ms': 0, 'hold_ms': 0},
            {'point': [3, 4], 'move_ms': 600, 'hold_ms': 0},
        ],
        '缓动': '线性',
    })


@pytest.mark.parametrize('platform', ('windows', 'android_adb'))
def test_click_hold_uses_the_same_atomic_input_contract_for_long_press(platform: str) -> None:
    driver = _FakeTargetDriver(platform)
    driver.execute('input.click', {
        'official.input.click.parameter.position': {'kind': 'point', 'x': 23, 'y': 45},
        'official.input.click.parameter.button': 'primary',
        'official.input.click.parameter.count': 1,
        'official.input.click.parameter.hold': 900,
        'official.input.click.parameter.interval': 0,
    }, lambda: False)
    assert driver.actions == [('drag', {
        '路径': [{'point': [23, 45], 'move_ms': 0, 'hold_ms': 900}],
        '缓动': '线性',
        '按键': '左键',
    })]


@pytest.mark.parametrize(
    ('platform', 'mode'),
    (
        ('windows', 'background'),
        ('windows', 'physical'),
        ('android_adb', 'target'),
    ),
)
def test_text_input_mode_is_delivered_only_to_a_compatible_target(platform: str, mode: str) -> None:
    driver = _FakeTargetDriver(platform)
    driver.execute('input.text', {
        'official.input.type_text.parameter.content': '测试',
        'official.input.type_text.parameter.mode': mode,
    }, lambda: False)
    assert driver.last_text_arguments == {'内容': '测试', '模式': mode}


@pytest.mark.parametrize(
    ('platform', 'mode'),
    (
        ('windows', 'target'),
        ('android_adb', 'background'),
        ('android_adb', 'physical'),
    ),
)
def test_text_input_mode_rejects_platform_mismatches_before_delivery(platform: str, mode: str) -> None:
    driver = _FakeTargetDriver(platform)
    with pytest.raises(RuntimeFailure) as raised:
        driver.execute('input.text', {
            'official.input.type_text.parameter.content': '测试',
            'official.input.type_text.parameter.mode': mode,
        }, lambda: False)
    assert raised.value.error_id == 'target.input_mode_unsupported'
    assert driver.actions == []


def _windows_driver_for_input(*, fallback: bool, desktop: bool = False) -> WindowsTargetDriver:
    driver = object.__new__(WindowsTargetDriver)
    driver.hwnd = 0 if desktop else 101
    driver.target = {
        'allow_physical_fallback': fallback or desktop,
        'work_area': {'mode': 'desktop' if desktop else 'client'},
    }
    driver._box = (0, 0, 800, 600)
    # These unit tests exercise delivery/fallback policy rather than Win32
    # geometry.  Keep them independent from whether pywin32 is installed on
    # the host and from the deliberately synthetic HWND above.
    driver._workspace_box = lambda: driver._box
    return driver


def test_windows_driver_resolves_minimized_window_for_workflow_restore(monkeypatch) -> None:
    calls = []

    def resolve(target, *, require_ready=True):
        calls.append(require_ready)
        return {'hwnd': 42, 'minimized': True}, 'captured_instance'

    monkeypatch.setattr('core.vnext.window_binding_v2.resolve_target_window', resolve)
    driver = object.__new__(WindowsTargetDriver)
    driver.target = {'type': 'windows', 'work_area': {'mode': 'client'}}

    assert driver._find_window() == 42
    assert calls == [False]


def test_windows_background_mode_never_silently_falls_back(monkeypatch) -> None:
    import core.services.background_input as background_input

    driver = _windows_driver_for_input(fallback=True)
    monkeypatch.setattr(background_input, 'background_text', lambda *_args, **_kwargs: {
        'ok': False, 'message': '窗口不接受后台消息',
    })
    monkeypatch.setattr(
        driver, '_run_physical',
        lambda *_args, **_kwargs: pytest.fail('仅后台模式不得回退物理输入'),
    )
    with pytest.raises(RuntimeFailure, match='窗口不接受后台消息'):
        driver.input_text({'内容': '测试', '模式': 'background'}, lambda: False)


def test_windows_auto_mode_logs_the_reason_when_it_falls_back(monkeypatch) -> None:
    import core.services.background_input as background_input

    driver = _windows_driver_for_input(fallback=True)
    monkeypatch.setattr(background_input, 'background_text', lambda *_args, **_kwargs: {
        'ok': False, 'message': '窗口不接受后台消息',
    })
    reasons: list[str] = []

    def physical(reason, _operation):
        reasons.append(reason)
        return {'ok': True, 'method': 'physical', 'message': f'{reason}，已使用物理输入'}

    monkeypatch.setattr(driver, '_run_physical', physical)
    result = driver.input_text({'内容': '测试', '模式': 'auto'}, lambda: False)
    assert reasons == ['后台文本输入失败（窗口不接受后台消息）']
    assert '已使用物理输入' in result['message']


def test_windows_explicit_physical_mode_respects_target_permission(monkeypatch) -> None:
    driver = _windows_driver_for_input(fallback=False)
    monkeypatch.setattr(
        driver, '_run_physical',
        lambda *_args, **_kwargs: pytest.fail('关闭物理输入时不得执行'),
    )
    with pytest.raises(RuntimeFailure) as raised:
        driver.input_text({'内容': '测试', '模式': 'physical'}, lambda: False)
    assert raised.value.error_id == 'target.physical_input_disabled'


@pytest.mark.parametrize(
    ('platform', 'mode', 'direction', 'expected_direction'),
    (
        ('windows', 'auto', 'left', '左'),
        ('windows', 'wheel', 'right', '右'),
        ('windows', 'touch', 'down', '下'),
        ('android_adb', 'auto', 'left', '左'),
        ('android_adb', 'touch', 'right', '右'),
    ),
)
def test_scroll_contract_exposes_only_executable_direction_mode_combinations(
    platform: str,
    mode: str,
    direction: str,
    expected_direction: str,
) -> None:
    driver = _FakeTargetDriver(platform)

    driver.execute('input.scroll', {
        'official.input.scroll.parameter.direction': direction,
        'official.input.scroll.parameter.mode': mode,
        'official.input.scroll.parameter.distance': 0.4,
        'official.input.scroll.parameter.start': {'kind': 'point', 'x': 12, 'y': 13},
        'official.input.scroll.parameter.duration': 250,
        'official.input.scroll.parameter.hold': 40,
    }, lambda: False)

    scroll = driver.actions[-1]
    assert scroll[0] == 'scroll'
    assert scroll[1]['方向'] == expected_direction
    assert scroll[1]['模式'] == mode
    assert scroll[1]['距离比例'] == 0.4


def test_adb_explicit_wheel_mode_is_rejected_before_input() -> None:
    driver = _FakeTargetDriver('android_adb')
    with pytest.raises(RuntimeFailure) as raised:
        driver.execute('input.scroll', {
            'official.input.scroll.parameter.direction': 'down',
            'official.input.scroll.parameter.mode': 'wheel',
        }, lambda: False)
    assert raised.value.error_id == 'target.scroll_mode_unsupported'
    assert driver.actions == []


@pytest.mark.parametrize('platform', ('windows', 'android_adb'))
def test_capture_and_find_return_stable_typed_records(platform: str) -> None:
    instructions = [
        _instruction(
            'capture', 'official.target.capture_frame', 'target.capture_frame', {},
            result_slot='frame',
        ),
        _instruction(
            'find', 'official.image.find', 'vision.find', {
                'official.image.find.parameter.image': {
                    'kind': 'asset_ref', 'asset_id': 'asset.login', 'asset_kind': 'image',
                },
                'official.image.find.parameter.similarity': 0.85,
                'official.image.find.parameter.region': {
                    'kind': 'rect', 'x': 0, 'y': 0, 'width': 100, 'height': 80,
                },
                'official.image.find.parameter.frame': {
                    'kind': 'reference', 'scope': 'local', 'symbol_id': 'frame',
                },
            }, result_slot='match',
        ),
    ]
    driver = _FakeTargetDriver(platform)
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_plan(instructions), driver=driver)['execution_id'])
    assert result['status'] == 'completed', result['error']
    match = result['variables']['match']
    assert match['image_match.field.center'] == {'kind': 'point', 'x': 20, 'y': 30}
    assert match['image_match.field.region']['width'] == 10
    assert match['image_match.field.similarity'] == 0.93
    assert ('asset', 'asset.login') in driver.actions
    assert ('find', ('frame-pixels', 0.85, [0, 0, 100, 80])) in driver.actions
    assert match['image_match.field.source_frame']['frame_ref.field.frame_id'] == 'frame.1'


def test_target_missing_and_platform_mismatch_are_stable_failures() -> None:
    click = _instruction('click', 'official.input.click', 'input.click', {
        'official.input.click.parameter.position': {'kind': 'point', 'x': 1, 'y': 2},
    })
    runtime = VNextRuntime(persist_event_log=False)
    missing = _terminal(runtime, runtime.start(_plan([click]))['execution_id'])
    assert missing['error_id'] == 'target.missing'
    assert missing['current_instruction_id'] == 'click'

    windows_only = {**click, 'platforms': ['windows']}
    runtime = VNextRuntime(persist_event_log=False)
    mismatch = _terminal(runtime, runtime.start(
        _plan([windows_only]), driver=_FakeTargetDriver('android_adb'),
    )['execution_id'])
    assert mismatch['error_id'] == 'target.platform_unsupported'
    assert mismatch['current_instruction_id'] == 'click'


def test_click_and_standard_wait_cancellation_do_not_fake_success() -> None:
    click = _instruction('click', 'official.input.click', 'input.click', {
        'official.input.click.parameter.position': {'kind': 'point', 'x': 1, 'y': 2},
        'official.input.click.parameter.count': 100,
        'official.input.click.parameter.interval': {'kind': 'duration', 'milliseconds': 50},
    })
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(_plan([click]), driver=_FakeTargetDriver('windows'))[
        'execution_id'
    ]
    time.sleep(0.03)
    runtime.cancel(execution_id)
    cancelled = _terminal(runtime, execution_id)
    assert cancelled['status'] == 'cancelled'
    assert cancelled['error_id'] == 'runtime.cancelled'
    assert cancelled['current_instruction_id'] == 'click'

    wait_visible = _instruction(
        'wait.visible', 'official.image.wait_visible',
        'standard.image.wait_visible', {
            'official.image.wait_visible.parameter.image': {
                'kind': 'asset_ref', 'asset_id': 'asset.test',
            },
            'official.image.wait_visible.parameter.timeout': {
                'kind': 'duration', 'milliseconds': 5000,
            },
            'official.image.wait_visible.parameter.interval': {
                'kind': 'duration', 'milliseconds': 100,
            },
            'official.image.wait_visible.parameter.stable_frames': 100,
        },
    )
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(
        _plan([wait_visible]), driver=_FakeTargetDriver('windows'),
    )['execution_id']
    time.sleep(0.03)
    runtime.cancel(execution_id)
    cancelled = _terminal(runtime, execution_id)
    assert cancelled['status'] == 'cancelled'
    assert cancelled['error_id'] == 'runtime.cancelled'
