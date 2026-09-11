from __future__ import annotations

from typing import Any

import pytest

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import ProgramDocument
from core.vnext.program_validation import validate_program_document
from core.vnext.runtime import RuntimeFailure, RuntimeSession, VNextRuntime
from core.vnext.standard_functions_v6 import (
    STANDARD_FUNCTION_DEFINITIONS,
    StandardRuntimeV6,
    require_standard_definition,
)


class _AtomicDriver:
    platform = 'windows'

    def __init__(
        self,
        *,
        images: list[dict[str, Any] | None] | None = None,
        texts: list[str] | None = None,
        windows: list[dict[str, Any] | None] | None = None,
        controls: list[dict[str, Any] | None] | None = None,
        image_scores: list[float | None] | None = None,
    ) -> None:
        self.images = list(images or [])
        self.texts = list(texts or [])
        self.windows = list(windows or [])
        self.controls = list(controls or [])
        self.image_scores = list(image_scores or [])
        self._image_diagnostic: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode in {'vision.find', 'text.recognize', 'input.click', 'window.find', 'control.find'}

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled):
        if cancelled():
            raise RuntimeFailure('cancelled', error_id='runtime.cancelled')
        self.calls.append((opcode, dict(arguments)))
        if opcode == 'vision.find':
            result = self.images.pop(0) if self.images else None
            score = self.image_scores.pop(0) if self.image_scores else (
                result.get('image_match.field.similarity') if isinstance(result, dict) else None
            )
            self._image_diagnostic = {'best_similarity': score, 'threshold': float(arguments.get('official.image.find.parameter.similarity', 0.85))}
            return result
        if opcode == 'text.recognize':
            text = self.texts.pop(0) if self.texts else ''
            return {
                'ocr_result.field.text': text,
                'ocr_result.field.lines': [],
                'ocr_result.field.region': {'kind': 'rect', 'x': 0, 'y': 0, 'width': 100, 'height': 50},
                'ocr_result.field.source_frame': {},
                'ocr_result.field.source_target': {'kind': 'target_ref', 'target_id': 'target.test'},
                'ocr_result.field.space_version': 'space.v1',
            }
        if opcode == 'window.find':
            return self.windows.pop(0) if self.windows else None
        if opcode == 'control.find':
            return self.controls.pop(0) if self.controls else None
        return {'ok': True}

    def image_match_diagnostic(self):
        return dict(self._image_diagnostic)


def _match(x: int = 20, y: int = 30) -> dict[str, Any]:
    return {
        'image_match.field.center': {'kind': 'point', 'x': x, 'y': y},
        'image_match.field.region': {'kind': 'rect', 'x': x - 5, 'y': y - 5, 'width': 10, 'height': 10},
        'image_match.field.similarity': 0.93,
        'image_match.field.source_asset': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
        'image_match.field.source_frame': {},
        'image_match.field.source_target': {'kind': 'target_ref', 'target_id': 'target.test'},
        'image_match.field.space_version': 'space.v1',
    }


def _args(function_id: str, **values: Any) -> dict[str, Any]:
    return {f'{function_id}.parameter.{name}': value for name, value in values.items()}


def _execute(function_id: str, driver: _AtomicDriver, **values: Any):
    contract = official_function_registry_v6.require(function_id)
    messages: list[str] = []
    result = StandardRuntimeV6().execute(
        contract.opcode,
        function_id,
        _args(function_id, **values),
        driver,
        lambda: False,
        messages.append,
        safe_checkpoint=lambda: None,
    )
    return result, messages


def test_all_fused_standard_functions_have_inspectable_atomic_program_documents() -> None:
    expected = {
        'official.target.wait_online',
        'official.window.wait_visible',
        'official.control.wait_visible', 'official.control.wait_hidden',
        'official.image.wait_visible', 'official.image.wait_hidden',
        'official.image.click_once', 'official.image.click_until_hidden',
        'official.image.click_position_until_visible',
        'official.image.click_position_until_hidden',
        'official.text.match', 'official.text.wait_visible',
    }
    assert set(STANDARD_FUNCTION_DEFINITIONS) == expected
    for function_id in sorted(expected):
        definition = require_standard_definition(function_id)
        assert isinstance(definition.document, ProgramDocument)
        assert definition.definition_id == f'standard.{function_id}'
        assert definition.document.function.function_id == function_id
        assert definition.semantic_policy
        assert validate_program_document(
            definition.document, official_function_registry_v6,
        ) == ()
        compiled = compile_program_document(
            definition.document, official_function_registry_v6,
        )
        assert compiled['valid'] is True, compiled['diagnostics']
        adapt_program_ecir_for_runtime(compiled['ecir'])
        for dependency in definition.atomic_dependencies:
            assert official_function_registry_v6.require(dependency).layer == 'atomic'
        assert official_function_registry_v6.require(function_id).standard_definition_id == definition.definition_id


def _execute_canonical(function_id: str, driver: _AtomicDriver, **values: Any):
    definition = require_standard_definition(function_id)
    compiled = compile_program_document(
        definition.document, official_function_registry_v6,
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    plan = adapt_program_ecir_for_runtime(compiled['ecir'])
    runtime = VNextRuntime(persist_event_log=False)
    session = RuntimeSession('canonical.standard', status='running')
    session._resume_gate.set()
    functions = {
        item['function_id']: item for item in plan['functions']
    }
    result = runtime._execute_function(
        session,
        function_id,
        functions,
        _args(function_id, **values),
        0,
        driver,
    )
    return result


@pytest.mark.parametrize(
    ('function_id', 'sequence', 'values'),
    (
        (
            'official.window.wait_visible',
            {'windows': [None, {
                'reference_id': 'window.test',
                'reference_type': 'window_ref',
                'window_ref.field.token': 'window.test',
                'window_ref.field.handle': 123,
                'window_ref.field.process_id': 456,
                'window_ref.field.title': '测试',
                'window_ref.field.class_name': 'TestWindow',
            }]},
            {'selector': {'window_selector.field.title': '测试'}, 'timeout': 50, 'interval': 1},
        ),
        (
            'official.image.wait_visible',
            {'images': [None, _match(10, 20), _match(11, 21)]},
            {
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'stable_frames': 2,
            },
        ),
        (
            'official.image.wait_hidden',
            {'images': [_match(), None, None]},
            {
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'stable_frames': 2,
            },
        ),
        (
            'official.image.click_once',
            {'images': [None, _match(44, 55)]},
            {
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'button': 'primary',
            },
        ),
        (
            'official.image.click_until_hidden',
            {'images': [_match(1, 2), None, None]},
            {
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'stable_frames': 2, 'button': 'primary',
            },
        ),
        (
            'official.image.click_position_until_visible',
            {'images': [None, _match(60, 70)]},
            {
                'position': {'kind': 'point', 'x': 8, 'y': 9},
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'stable_frames': 1, 'button': 'primary',
            },
        ),
        (
            'official.image.click_position_until_hidden',
            {'images': [_match(60, 70), None, None]},
            {
                'position': {'kind': 'point', 'x': 8, 'y': 9},
                'image': {'kind': 'asset_ref', 'asset_id': 'asset.test'},
                'similarity': 0.85, 'region': None, 'timeout': 50,
                'interval': 1, 'stable_frames': 2, 'button': 'primary',
            },
        ),
        (
            'official.text.match',
            {'texts': ['登录成功']},
            {'text': '登录', 'mode': 'contains', 'region': None, 'language': 'auto'},
        ),
        (
            'official.text.wait_visible',
            {'texts': ['未命中', '登录成功', '登录成功']},
            {
                'text': '登录', 'mode': 'contains', 'region': None,
                'language': 'auto', 'timeout': 50, 'interval': 1,
                'stable_frames': 2,
            },
        ),
    ),
)
def test_fused_standard_runtime_is_result_and_atomic_trace_equivalent_to_canonical_program(
    function_id: str,
    sequence: dict[str, list[Any]],
    values: dict[str, Any],
) -> None:
    canonical_driver = _AtomicDriver(**sequence)
    fused_driver = _AtomicDriver(**sequence)
    canonical_result = _execute_canonical(
        function_id, canonical_driver, **values,
    )
    fused_result, fused_messages = _execute(
        function_id, fused_driver, **values,
    )
    assert fused_result == canonical_result
    assert fused_driver.calls == canonical_driver.calls
    assert fused_messages, '融合运行时必须保留可诊断的标准函数日志'


def test_image_waits_use_a_fresh_atomic_check_and_consecutive_stable_frames() -> None:
    first, second = _match(10, 11), _match(12, 13)
    driver = _AtomicDriver(images=[None, first, second])
    result, messages = _execute(
        'official.image.wait_visible', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        similarity=0.85, region=None, timeout=100, interval=1, stable_frames=2,
    )
    assert result == second
    assert [name for name, _ in driver.calls] == ['vision.find'] * 3
    assert '稳定 2 帧' in messages[-1]

    driver = _AtomicDriver(images=[first, None, None])
    hidden, _ = _execute(
        'official.image.wait_hidden', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        timeout=100, interval=1, stable_frames=2,
    )
    assert hidden is True
    assert [name for name, _ in driver.calls] == ['vision.find'] * 3


def test_image_click_standards_use_match_center_and_report_timeout_without_exception() -> None:
    found = _match(44, 55)
    driver = _AtomicDriver(images=[None, found])
    result, _ = _execute(
        'official.image.click_once', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        timeout=100, interval=1, button='primary',
    )
    assert result == found
    click = [arguments for opcode, arguments in driver.calls if opcode == 'input.click']
    assert click[0]['official.input.click.parameter.position'] == {
        'kind': 'point', 'x': 44, 'y': 55,
    }

    driver = _AtomicDriver(images=[_match(1, 2), _match(3, 4), None, None])
    result, _ = _execute(
        'official.image.click_until_hidden', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        timeout=100, interval=1, stable_frames=2, button='primary',
    )
    assert result['image_click_loop_result.field.hidden'] is True
    assert result['image_click_loop_result.field.click_count'] == 2
    assert len([item for item in driver.calls if item[0] == 'input.click']) == 2

    driver = _AtomicDriver(images=[None])
    missing, _ = _execute(
        'official.image.wait_visible', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        timeout=0, interval=1, stable_frames=1,
    )
    assert missing is None
    assert [item[0] for item in driver.calls] == ['vision.find']

    driver = _AtomicDriver(images=[None], image_scores=[0.842])
    missing, messages = _execute(
        'official.image.wait_visible', driver,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        similarity=0.85, timeout=0, interval=1, stable_frames=1,
    )
    assert missing is None
    assert '最高相似度 0.842，阈值 0.850' in messages[-1]


@pytest.mark.parametrize(
    ('function_id', 'images', 'stable_frames'),
    (
        ('official.image.click_position_until_visible', [_match()], 1),
        ('official.image.click_position_until_hidden', [None, None], 2),
    ),
)
def test_click_position_conditions_observe_before_act_and_can_return_without_clicking(
    function_id: str,
    images: list[dict[str, Any] | None],
    stable_frames: int,
) -> None:
    driver = _AtomicDriver(images=images)
    result, messages = _execute(
        function_id, driver,
        position={'kind': 'point', 'x': 111, 'y': 222},
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        similarity=0.85, region=None, timeout=100, interval=1,
        stable_frames=stable_frames, button='primary',
    )

    assert result['image_click_condition_result.field.reached'] is True
    assert result['image_click_condition_result.field.click_count'] == 0
    assert not [item for item in driver.calls if item[0] == 'input.click']
    assert '点击 0 次' in messages[-1]


@pytest.mark.parametrize(
    ('function_id', 'images', 'stable_frames'),
    (
        ('official.image.click_position_until_visible', [None, _match(30, 40)], 1),
        ('official.image.click_position_until_hidden', [_match(30, 40), None, None], 2),
    ),
)
def test_click_position_conditions_click_only_the_configured_point(
    function_id: str,
    images: list[dict[str, Any] | None],
    stable_frames: int,
) -> None:
    point = {'kind': 'point', 'x': 111, 'y': 222}
    driver = _AtomicDriver(images=images)
    result, _ = _execute(
        function_id, driver,
        position=point,
        image={'kind': 'asset_ref', 'asset_id': 'asset.test'},
        similarity=0.85, region=None, timeout=100, interval=1,
        stable_frames=stable_frames, button='primary',
    )

    assert result['image_click_condition_result.field.reached'] is True
    assert result['image_click_condition_result.field.click_count'] == 1
    clicks = [arguments for opcode, arguments in driver.calls if opcode == 'input.click']
    assert [item['official.input.click.parameter.position'] for item in clicks] == [point]


@pytest.mark.parametrize(
    ('mode', 'expected', 'actual', 'matched'),
    (
        ('exact', '登录成功', '登录成功', True),
        ('exact', '登录', '登录成功', False),
        ('contains', '登录', '登录成功', True),
        ('regex', r'登录\s*成功', '登录 成功', True),
    ),
)
def test_text_match_modes_return_the_ocr_record_or_normal_empty(mode, expected, actual, matched) -> None:
    driver = _AtomicDriver(texts=[actual])
    result, _ = _execute(
        'official.text.match', driver,
        text=expected, mode=mode, region=None, language='auto',
    )
    assert (result is not None) is matched
    assert [item[0] for item in driver.calls] == ['text.recognize']


def test_text_wait_stability_regex_validation_window_wait_and_cancellation() -> None:
    driver = _AtomicDriver(texts=['未命中', '登录成功', '登录成功'])
    result, messages = _execute(
        'official.text.wait_visible', driver,
        text='登录', mode='contains', region=None, language='auto',
        timeout=100, interval=1, stable_frames=2,
    )
    assert result['ocr_result.field.text'] == '登录成功'
    assert '稳定 2 帧' in messages[-1]

    driver = _AtomicDriver(texts=['anything'])
    with pytest.raises(RuntimeFailure) as invalid:
        _execute(
            'official.text.match', driver,
            text='[', mode='regex', region=None, language='auto',
        )
    assert invalid.value.error_id == 'text.regex_invalid'
    assert driver.calls == []

    window = {'window_ref.field.token': 'window.test'}
    driver = _AtomicDriver(windows=[None, window])
    result, _ = _execute(
        'official.window.wait_visible', driver,
        selector={'window_selector.field.title': '测试'}, timeout=100, interval=1,
    )
    assert result == window

    control = {'control_ref.field.token': 'control.test'}
    driver = _AtomicDriver(controls=[None, control])
    result, _ = _execute(
        'official.control.wait_visible', driver,
        selector={'control_selector.field.provider': 'windows_uia'}, timeout=100, interval=1,
    )
    assert result == control

    driver = _AtomicDriver(controls=[control, None])
    result, _ = _execute(
        'official.control.wait_hidden', driver,
        selector={'control_selector.field.provider': 'windows_uia'}, timeout=100, interval=1,
    )
    assert result is True

    with pytest.raises(RuntimeFailure) as cancelled:
        StandardRuntimeV6().execute(
            'standard.image.wait_visible', 'official.image.wait_visible',
            _args('official.image.wait_visible', image={'kind': 'asset_ref', 'asset_id': 'asset.test'}),
            _AtomicDriver(images=[None]), lambda: True, lambda _message: None,
            safe_checkpoint=lambda: None,
        )
    assert cancelled.value.error_id == 'runtime.cancelled'
