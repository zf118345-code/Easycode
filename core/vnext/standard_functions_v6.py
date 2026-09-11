"""Inspectable official standard functions and their fused runtime.

The inspectable definition of every standard function remains a normal,
compiler-validated ``ProgramDocument``.  Definitions use official atomic calls
plus the same structured control statements and approved pure-value operations
available to project functions.  The runtime uses a small fused executor so
visual polling does not allocate an ECIR call frame for every check.
``STANDARD_FUNCTION_DEFINITIONS`` exposes the canonical document and
``semantic_policy`` used by the equivalence harness; the fused path must not
introduce an observable primitive that is absent from that definition.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from .program_types import (
    AssignmentStatement,
    BoolValue,
    CallStatement,
    ComparisonValue,
    DurationValue,
    IfStatement,
    IntValue,
    LocalAssignmentTarget,
    LoopStatement,
    MemberAccessValue,
    NullValue,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    PureOperationValue,
    RecordValue,
    ResultBinding,
    ReturnStatement,
    SymbolReferenceValue,
    ValueNode,
)
from .runtime import RuntimeFailure


def _parameter(function_id: str, name: str, value_type: str) -> ProgramParameter:
    return ProgramParameter(
        parameter_id=f'{function_id}.parameter.{name}',
        symbol_id=f'{function_id}.symbol.parameter.{name}',
        display_name=name,
        value_type=value_type,
        # A standard call resolves its public optional defaults before entering
        # this canonical body.  The body therefore receives a complete,
        # strongly typed argument frame and never owns a second set of defaults.
        required=True,
    )


def _reference(function_id: str, name: str, value_type: str, suffix: str) -> SymbolReferenceValue:
    return SymbolReferenceValue(
        value_id=f'{function_id}.value.{suffix}',
        symbol_id=f'{function_id}.symbol.parameter.{name}',
        value_type=value_type,
    )


def _call(
    owner: str,
    suffix: str,
    function_id: str,
    bindings: tuple[tuple[str, str, str], ...],
    *,
    result: tuple[str, str, str] | None = None,
    extra_arguments: dict[str, ValueNode] | None = None,
) -> CallStatement:
    arguments = {
        f'{function_id}.parameter.{target_name}': _reference(
            owner, source_name, value_type, f'{suffix}.{target_name}',
        )
        for target_name, source_name, value_type in bindings
    }
    arguments.update(extra_arguments or {})
    return CallStatement(
        statement_id=f'{owner}.statement.{suffix}',
        function_id=function_id,
        arguments=arguments,
        result_binding=(
            ResultBinding(symbol_id=result[0], display_name=result[1], value_type=result[2])
            if result is not None else None
        ),
        step_label=suffix.replace('_', ' '),
    )


def _symbol(owner: str, suffix: str, symbol_id: str, value_type: str) -> SymbolReferenceValue:
    return SymbolReferenceValue(
        value_id=f'{owner}.value.{suffix}', symbol_id=symbol_id, value_type=value_type,
    )


def _operation(
    owner: str,
    suffix: str,
    operation_id: str,
    result_type: str,
    inputs: dict[str, ValueNode],
) -> PureOperationValue:
    return PureOperationValue(
        value_id=f'{owner}.value.{suffix}',
        operation_id=operation_id,
        result_type=result_type,
        inputs={f'{operation_id}.input.{name}': value for name, value in inputs.items()},
    )


def _assign(
    owner: str,
    suffix: str,
    symbol_id: str,
    display_name: str,
    value_type: str,
    value: ValueNode,
    *,
    declare: bool,
) -> AssignmentStatement:
    return AssignmentStatement(
        statement_id=f'{owner}.statement.{suffix}',
        target=LocalAssignmentTarget(
            symbol_id=symbol_id,
            display_name=display_name,
            value_type=value_type,
            declare=declare,
        ),
        value=value,
        step_label=suffix.replace('_', ' '),
    )


def _number_change(
    owner: str, suffix: str, symbol_id: str, display_name: str, operation_id: str,
) -> AssignmentStatement:
    return _assign(
        owner, suffix, symbol_id, display_name, 'int64',
        _operation(owner, f'{suffix}.operation', operation_id, 'int64', {
            'left': _symbol(owner, f'{suffix}.current', symbol_id, 'int64'),
            'right': IntValue(value_id=f'{owner}.value.{suffix}.one', value=1),
        }),
        declare=False,
    )


def _compare_symbol_parameter(
    owner: str, suffix: str, symbol_id: str, parameter_name: str, operator: str,
) -> ComparisonValue:
    return ComparisonValue(
        value_id=f'{owner}.value.{suffix}',
        operator=operator,
        left=_symbol(owner, f'{suffix}.left', symbol_id, 'int64'),
        right=_reference(owner, parameter_name, 'int64', f'{suffix}.right'),
    )


def _has_value(owner: str, suffix: str, symbol_id: str, value_type: str) -> ComparisonValue:
    return ComparisonValue(
        value_id=f'{owner}.value.{suffix}',
        operator='ne',
        left=_symbol(owner, f'{suffix}.result', symbol_id, value_type),
        right=NullValue(value_id=f'{owner}.value.{suffix}.null'),
    )


def _remaining_setup(owner: str) -> tuple[AssignmentStatement, str]:
    remaining = f'{owner}.symbol.remaining_checks'
    return (
        _assign(
            owner, 'prepare_check_budget', remaining, '剩余检查次数', 'int64',
            _operation(owner, 'poll_count', 'core.duration_poll_count.v1', 'int64', {
                'timeout': _reference(owner, 'timeout', 'duration', 'poll_count.timeout'),
                'interval': _reference(owner, 'interval', 'duration', 'poll_count.interval'),
            }),
            declare=True,
        ),
        remaining,
    )


def _remaining_condition(owner: str, remaining: str, suffix: str) -> ComparisonValue:
    return ComparisonValue(
        value_id=f'{owner}.value.{suffix}.has_remaining_checks', operator='gt',
        left=_symbol(owner, f'{suffix}.remaining_checks', remaining, 'int64'),
        right=IntValue(value_id=f'{owner}.value.{suffix}.zero_checks', value=0),
    )


def _wait_if_remaining(owner: str, remaining: str, suffix: str) -> tuple[AssignmentStatement, IfStatement]:
    decrement = _number_change(
        owner, f'{suffix}_decrement_budget', remaining, '剩余检查次数',
        'core.number_subtract.v1',
    )
    wait = _call(owner, f'{suffix}_wait_interval', 'official.wait.duration', (
        ('duration', 'interval', 'duration'),
    ))
    return decrement, IfStatement(
        statement_id=f'{owner}.statement.{suffix}_wait_if_remaining',
        condition=_remaining_condition(owner, remaining, f'{suffix}.wait'),
        then_statements=(wait,),
        step_label='仍有检查次数时等待',
    )


def _return(owner: str, suffix: str, value: ValueNode) -> ReturnStatement:
    return ReturnStatement(
        statement_id=f'{owner}.statement.{suffix}', value=value,
        step_label=suffix.replace('_', ' '),
    )


def _image_find(owner: str, suffix: str, result_symbol: str) -> CallStatement:
    return _call(owner, suffix, 'official.image.find', (
        ('image', 'image', 'asset_ref<image>'),
        ('similarity', 'similarity', 'percentage'),
        ('region', 'region', 'optional<rect>'),
    ), result=(result_symbol, '图像匹配', 'optional<image_match>'))


def _image_center(owner: str, suffix: str, result_symbol: str) -> MemberAccessValue:
    return MemberAccessValue(
        value_id=f'{owner}.value.{suffix}',
        source=_symbol(owner, f'{suffix}.source', result_symbol, 'optional<image_match>'),
        field_id='image_match.field.center',
        result_type='point',
    )


def _click_match(owner: str, suffix: str, result_symbol: str) -> CallStatement:
    return _call(
        owner, suffix, 'official.input.click',
        (('button', 'button', 'enum<pointer_button>'),),
        extra_arguments={
            'official.input.click.parameter.position': _image_center(
                owner, f'{suffix}.center', result_symbol,
            ),
            'official.input.click.parameter.count': IntValue(
                value_id=f'{owner}.value.{suffix}.count', value=1,
            ),
            'official.input.click.parameter.interval': DurationValue(
                value_id=f'{owner}.value.{suffix}.interval', milliseconds=0,
            ),
        },
    )


def _click_position(owner: str, suffix: str) -> CallStatement:
    return _call(
        owner, suffix, 'official.input.click',
        (('position', 'position', 'point'), ('button', 'button', 'enum<pointer_button>')),
        extra_arguments={
            'official.input.click.parameter.count': IntValue(
                value_id=f'{owner}.value.{suffix}.count', value=1,
            ),
            'official.input.click.parameter.interval': DurationValue(
                value_id=f'{owner}.value.{suffix}.interval', milliseconds=0,
            ),
        },
    )


def _stable_setup(owner: str) -> tuple[AssignmentStatement, str]:
    stable = f'{owner}.symbol.stable_frames'
    return (
        _assign(
            owner, 'initialize_stable_frames', stable, '连续稳定帧', 'int64',
            IntValue(value_id=f'{owner}.value.stable_zero', value=0), declare=True,
        ),
        stable,
    )


def _stable_increment(owner: str, stable: str, suffix: str) -> AssignmentStatement:
    return _number_change(
        owner, suffix, stable, '连续稳定帧', 'core.number_add.v1',
    )


def _stable_reset(owner: str, stable: str, suffix: str) -> AssignmentStatement:
    return _assign(
        owner, suffix, stable, '连续稳定帧', 'int64',
        IntValue(value_id=f'{owner}.value.{suffix}.zero', value=0), declare=False,
    )


def _stable_reached(owner: str, stable: str, suffix: str) -> ComparisonValue:
    return _compare_symbol_parameter(owner, suffix, stable, 'stable_frames', 'gte')


@dataclass(frozen=True)
class StandardFunctionDefinitionV6:
    definition_id: str
    function_id: str
    document: ProgramDocument
    atomic_dependencies: tuple[str, ...]
    semantic_policy: tuple[str, ...]


def _definition(
    function_id: str,
    parameters: tuple[tuple[str, str], ...],
    return_type: str,
    statements: tuple[Any, ...],
    dependencies: tuple[str, ...],
    policy: tuple[str, ...],
) -> StandardFunctionDefinitionV6:
    document = ProgramDocument(
        document_id=f'standard.{function_id}',
        function=ProgramFunction(
            function_id=function_id,
            display_name=function_id,
            parameters=tuple(_parameter(function_id, name, value_type) for name, value_type in parameters),
            return_type=return_type,
            statements=statements,
        ),
    )
    return StandardFunctionDefinitionV6(
        definition_id=document.document_id,
        function_id=function_id,
        document=document,
        atomic_dependencies=dependencies,
        semantic_policy=policy,
    )


def _click_position_condition_definition(
    function_id: str, *, wait_visible: bool,
) -> StandardFunctionDefinitionV6:
    """Build the canonical observe-before-act fixed-point visual loop."""

    owner = function_id
    setup, remaining = _remaining_setup(owner)
    stable_setup, stable = _stable_setup(owner)
    result_symbol = f'{owner}.symbol.image_result'
    click_count = f'{owner}.symbol.click_count'
    last_match = f'{owner}.symbol.last_match'
    click_setup = _assign(
        owner, 'initialize_click_count', click_count, '点击次数', 'int64',
        IntValue(value_id=f'{owner}.value.click_zero', value=0), declare=True,
    )
    last_setup = _assign(
        owner, 'initialize_last_match', last_match, '最后匹配', 'optional<image_match>',
        NullValue(value_id=f'{owner}.value.last_match_null'), declare=True,
    )

    def report(reached: bool, suffix: str) -> RecordValue:
        return RecordValue(
            value_id=f'{owner}.value.{suffix}', record_type='image_click_condition_result',
            fields={
                'image_click_condition_result.field.reached': BoolValue(
                    value_id=f'{owner}.value.{suffix}.reached', value=reached,
                ),
                'image_click_condition_result.field.click_count': _symbol(
                    owner, f'{suffix}.click_count', click_count, 'int64',
                ),
                'image_click_condition_result.field.last_match': _symbol(
                    owner, f'{suffix}.last_match', last_match, 'optional<image_match>',
                ),
            },
        )

    reached_statements: tuple[Any, ...] = (
        _stable_increment(owner, stable, 'increment_target_frames'),
    )
    if wait_visible:
        reached_statements += (_assign(
            owner, 'save_last_match', last_match, '最后匹配', 'optional<image_match>',
            _symbol(owner, 'last_match_source', result_symbol, 'optional<image_match>'),
            declare=False,
        ),)
    reached_statements += (IfStatement(
        statement_id=f'{owner}.statement.return_when_reached',
        condition=_stable_reached(owner, stable, 'target_is_stable'),
        then_statements=(_return(owner, 'return_reached_report', report(True, 'reached_report')),),
    ),)

    click_statements: tuple[Any, ...] = (
        _stable_reset(owner, stable, 'reset_target_frames'),
    )
    if not wait_visible:
        click_statements += (_assign(
            owner, 'save_last_match', last_match, '最后匹配', 'optional<image_match>',
            _symbol(owner, 'last_match_source', result_symbol, 'optional<image_match>'),
            declare=False,
        ),)
    click_statements += (
        _click_position(owner, 'click_fixed_position'),
        _number_change(
            owner, 'increment_click_count', click_count, '点击次数', 'core.number_add.v1',
        ),
    )

    found = _has_value(owner, 'image_found', result_symbol, 'optional<image_match>')
    if wait_visible:
        then_statements, otherwise_statements = reached_statements, click_statements
    else:
        then_statements, otherwise_statements = click_statements, reached_statements
    decrement, wait = _wait_if_remaining(owner, remaining, 'image_click_position_condition')
    target = 'visible' if wait_visible else 'hidden'
    return _definition(
        owner,
        (('position', 'point'),) + _IMAGE_PARAMETERS
        + (('stable_frames', 'int64'), ('button', 'enum<pointer_button>')),
        'image_click_condition_result',
        (setup, stable_setup, click_setup, last_setup, LoopStatement(
            statement_id=f'{owner}.statement.poll', mode='while',
            source=_remaining_condition(owner, remaining, 'image_click_position_condition.loop'),
            body=(
                _image_find(owner, 'find_fresh_frame', result_symbol),
                IfStatement(
                    statement_id=f'{owner}.statement.observe_before_click',
                    condition=found,
                    then_statements=then_statements,
                    otherwise_statements=otherwise_statements,
                ),
                decrement, wait,
            ),
        ), _return(owner, 'return_condition_timeout', report(False, 'timeout_report'))),
        ('official.image.find', 'official.input.click', 'official.wait.duration'),
        (
            'fresh_check', 'observe_before_act', 'click_fixed_position',
            f'consecutive_{target}', 'monotonic_deadline', 'normal_timeout', 'cancellable',
        ),
    )


_IMAGE_PARAMETERS = (
    ('image', 'asset_ref<image>'), ('similarity', 'percentage'),
    ('region', 'optional<rect>'), ('timeout', 'duration'),
    ('interval', 'duration'),
)
_TEXT_PARAMETERS = (
    ('text', 'string'), ('mode', 'enum<text_match_mode>'),
    ('region', 'optional<rect>'), ('language', 'enum<ocr_language>'),
)


def _build_definitions() -> dict[str, StandardFunctionDefinitionV6]:
    values: list[StandardFunctionDefinitionV6] = []

    owner = 'official.target.wait_online'
    remaining = f'{owner}.symbol.remaining_checks'
    interval = DurationValue(value_id=f'{owner}.value.interval', milliseconds=100)
    setup = _assign(
        owner, 'prepare_check_budget', remaining, '剩余检查次数', 'int64',
        _operation(owner, 'poll_count', 'core.duration_poll_count.v1', 'int64', {
            'timeout': _reference(owner, 'timeout', 'duration', 'poll_count.timeout'),
            'interval': interval,
        }), declare=True,
    )
    status_symbol = f'{owner}.symbol.target_status'
    decrement = _number_change(
        owner, 'target_decrement_budget', remaining, '剩余检查次数',
        'core.number_subtract.v1',
    )
    target_wait = IfStatement(
        statement_id=f'{owner}.statement.target_wait_if_remaining',
        condition=_remaining_condition(owner, remaining, 'target.wait'),
        then_statements=(_call(
            owner, 'target_wait_interval', 'official.wait.duration', (),
            extra_arguments={
                'official.wait.duration.parameter.duration': DurationValue(
                    value_id=f'{owner}.value.target_wait_interval', milliseconds=100,
                ),
            },
        ),),
    )
    online = MemberAccessValue(
        value_id=f'{owner}.value.target_online',
        source=_symbol(owner, 'target_status_source', status_symbol, 'target_info'),
        field_id='target_info.field.online', result_type='bool',
    )
    values.append(_definition(
        owner,
        (('target', 'target_ref'), ('timeout', 'duration')),
        'optional<target_info>',
        (setup, LoopStatement(
            statement_id=f'{owner}.statement.poll', mode='while',
            source=_remaining_condition(owner, remaining, 'target.loop'),
            body=(
                _call(owner, 'read_target_status', 'official.target.read_status', (
                    ('target', 'target', 'target_ref'),
                ), result=(status_symbol, '目标状态', 'target_info')),
                IfStatement(
                    statement_id=f'{owner}.statement.return_if_online', condition=online,
                    then_statements=(_return(
                        owner, 'return_online_target',
                        _symbol(owner, 'online_target_return', status_symbol, 'target_info'),
                    ),),
                ),
                decrement, target_wait,
            ),
        ), _return(owner, 'return_target_timeout', NullValue(
            value_id=f'{owner}.value.timeout_null',
        ))),
        ('official.target.read_status', 'official.wait.duration'),
        ('fresh_check', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
    ))

    owner = 'official.window.wait_visible'
    setup, remaining = _remaining_setup(owner)
    result_symbol = f'{owner}.symbol.window_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'window')
    values.append(
        _definition(
            owner,
            (('selector', 'window_selector'), ('timeout', 'duration'), ('interval', 'duration')),
            'optional<window_ref>',
            (setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'window.loop'),
                body=(
                    _call(owner, 'find_current_window', 'official.window.find', (
                        ('selector', 'selector', 'window_selector'),
                    ), result=(result_symbol, '窗口结果', 'optional<window_ref>')),
                    IfStatement(
                        statement_id=f'{owner}.statement.return_if_found',
                        condition=_has_value(owner, 'window_found', result_symbol, 'optional<window_ref>'),
                        then_statements=(_return(
                            owner, 'return_window',
                            _symbol(owner, 'window_return', result_symbol, 'optional<window_ref>'),
                        ),),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_window_timeout', NullValue(
                value_id=f'{owner}.value.timeout_null',
            ))),
            ('official.window.find',),
            ('fresh_check', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )

    owner = 'official.control.wait_visible'
    setup, remaining = _remaining_setup(owner)
    result_symbol = f'{owner}.symbol.control_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'control_visible')
    values.append(
        _definition(
            owner,
            (('selector', 'control_selector'), ('timeout', 'duration'), ('interval', 'duration')),
            'optional<control_ref>',
            (setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'control_visible.loop'),
                body=(
                    _call(owner, 'find_current_control', 'official.control.find', (
                        ('selector', 'selector', 'control_selector'),
                    ), result=(result_symbol, '控件结果', 'optional<control_ref>')),
                    IfStatement(
                        statement_id=f'{owner}.statement.return_if_found',
                        condition=_has_value(owner, 'control_found', result_symbol, 'optional<control_ref>'),
                        then_statements=(_return(
                            owner, 'return_control',
                            _symbol(owner, 'control_return', result_symbol, 'optional<control_ref>'),
                        ),),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_control_timeout', NullValue(
                value_id=f'{owner}.value.timeout_null',
            ))),
            ('official.control.find', 'official.wait.duration'),
            ('fresh_check', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )

    owner = 'official.control.wait_hidden'
    setup, remaining = _remaining_setup(owner)
    result_symbol = f'{owner}.symbol.control_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'control_hidden')
    values.append(
        _definition(
            owner,
            (('selector', 'control_selector'), ('timeout', 'duration'), ('interval', 'duration')),
            'bool',
            (setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'control_hidden.loop'),
                body=(
                    _call(owner, 'find_current_control', 'official.control.find', (
                        ('selector', 'selector', 'control_selector'),
                    ), result=(result_symbol, '控件结果', 'optional<control_ref>')),
                    IfStatement(
                        statement_id=f'{owner}.statement.return_if_hidden',
                        condition=ComparisonValue(
                            value_id=f'{owner}.value.control_hidden', operator='eq',
                            left=_symbol(
                                owner, 'control_hidden.result', result_symbol, 'optional<control_ref>',
                            ),
                            right=NullValue(value_id=f'{owner}.value.control_hidden.null'),
                        ),
                        then_statements=(_return(
                            owner, 'return_hidden',
                            BoolValue(value_id=f'{owner}.value.hidden_true', value=True),
                        ),),
                    ),
                    decrement, wait,
                ),
            ), _return(
                owner, 'return_hidden_timeout',
                BoolValue(value_id=f'{owner}.value.hidden_false', value=False),
            )),
            ('official.control.find', 'official.wait.duration'),
            ('fresh_check', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )

    owner = 'official.image.wait_visible'
    setup, remaining = _remaining_setup(owner)
    stable_setup, stable = _stable_setup(owner)
    result_symbol = f'{owner}.symbol.image_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'image_visible')
    found = _has_value(owner, 'image_found', result_symbol, 'optional<image_match>')
    values.append(
        _definition(
            owner, _IMAGE_PARAMETERS + (('stable_frames', 'int64'),),
            'optional<image_match>',
            (setup, stable_setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'image_visible.loop'),
                body=(
                    _image_find(owner, 'find_fresh_frame', result_symbol),
                    IfStatement(
                        statement_id=f'{owner}.statement.track_stability',
                        condition=found,
                        then_statements=(
                            _stable_increment(owner, stable, 'increment_visible_frames'),
                            IfStatement(
                                statement_id=f'{owner}.statement.return_when_stable',
                                condition=_stable_reached(owner, stable, 'visible_is_stable'),
                                then_statements=(_return(
                                    owner, 'return_visible_match',
                                    _symbol(owner, 'visible_match_return', result_symbol, 'optional<image_match>'),
                                ),),
                            ),
                        ),
                        otherwise_statements=(_stable_reset(owner, stable, 'reset_visible_frames'),),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_visible_timeout', NullValue(
                value_id=f'{owner}.value.timeout_null',
            ))),
            ('official.image.find', 'official.wait.duration'),
            ('fresh_check', 'consecutive_matches', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )

    owner = 'official.image.wait_hidden'
    setup, remaining = _remaining_setup(owner)
    stable_setup, stable = _stable_setup(owner)
    result_symbol = f'{owner}.symbol.image_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'image_hidden')
    found = _has_value(owner, 'image_found', result_symbol, 'optional<image_match>')
    values.append(
        _definition(
            owner, _IMAGE_PARAMETERS + (('stable_frames', 'int64'),),
            'bool',
            (setup, stable_setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'image_hidden.loop'),
                body=(
                    _image_find(owner, 'find_fresh_frame', result_symbol),
                    IfStatement(
                        statement_id=f'{owner}.statement.track_stability',
                        condition=found,
                        then_statements=(_stable_reset(owner, stable, 'reset_hidden_frames'),),
                        otherwise_statements=(
                            _stable_increment(owner, stable, 'increment_hidden_frames'),
                            IfStatement(
                                statement_id=f'{owner}.statement.return_when_stable',
                                condition=_stable_reached(owner, stable, 'hidden_is_stable'),
                                then_statements=(_return(
                                    owner, 'return_hidden', BoolValue(
                                        value_id=f'{owner}.value.hidden_true', value=True,
                                    ),
                                ),),
                            ),
                        ),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_hidden_timeout', BoolValue(
                value_id=f'{owner}.value.hidden_false', value=False,
            ))),
            ('official.image.find', 'official.wait.duration'),
            ('fresh_check', 'consecutive_misses', 'monotonic_deadline', 'false_on_timeout', 'cancellable'),
        )
    )

    owner = 'official.image.click_once'
    setup, remaining = _remaining_setup(owner)
    result_symbol = f'{owner}.symbol.image_result'
    decrement, wait = _wait_if_remaining(owner, remaining, 'image_click_once')
    values.append(
        _definition(
            owner, _IMAGE_PARAMETERS + (('button', 'enum<pointer_button>'),),
            'optional<image_match>',
            (setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'image_click_once.loop'),
                body=(
                    _image_find(owner, 'find_fresh_frame', result_symbol),
                    IfStatement(
                        statement_id=f'{owner}.statement.click_if_found',
                        condition=_has_value(owner, 'image_found', result_symbol, 'optional<image_match>'),
                        then_statements=(
                            _click_match(owner, 'click_match_center', result_symbol),
                            _return(
                                owner, 'return_clicked_match',
                                _symbol(owner, 'clicked_match_return', result_symbol, 'optional<image_match>'),
                            ),
                        ),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_click_timeout', NullValue(
                value_id=f'{owner}.value.timeout_null',
            ))),
            ('official.image.find', 'official.input.click', 'official.wait.duration'),
            ('fresh_check', 'click_match_center_once', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )

    owner = 'official.image.click_until_hidden'
    setup, remaining = _remaining_setup(owner)
    stable_setup, stable = _stable_setup(owner)
    result_symbol = f'{owner}.symbol.image_result'
    click_count = f'{owner}.symbol.click_count'
    last_match = f'{owner}.symbol.last_match'
    click_setup = _assign(
        owner, 'initialize_click_count', click_count, '点击次数', 'int64',
        IntValue(value_id=f'{owner}.value.click_zero', value=0), declare=True,
    )
    last_setup = _assign(
        owner, 'initialize_last_match', last_match, '最后匹配', 'optional<image_match>',
        NullValue(value_id=f'{owner}.value.last_match_null'), declare=True,
    )

    def click_report(hidden: bool, suffix: str) -> RecordValue:
        return RecordValue(
            value_id=f'{owner}.value.{suffix}', record_type='image_click_loop_result',
            fields={
                'image_click_loop_result.field.hidden': BoolValue(
                    value_id=f'{owner}.value.{suffix}.hidden', value=hidden,
                ),
                'image_click_loop_result.field.click_count': _symbol(
                    owner, f'{suffix}.click_count', click_count, 'int64',
                ),
                'image_click_loop_result.field.last_match': _symbol(
                    owner, f'{suffix}.last_match', last_match, 'optional<image_match>',
                ),
            },
        )

    decrement, wait = _wait_if_remaining(owner, remaining, 'image_click_until_hidden')
    values.append(
        _definition(
            owner,
            _IMAGE_PARAMETERS + (('stable_frames', 'int64'), ('button', 'enum<pointer_button>')),
            'image_click_loop_result',
            (setup, stable_setup, click_setup, last_setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'image_click_until_hidden.loop'),
                body=(
                    _image_find(owner, 'find_fresh_frame', result_symbol),
                    IfStatement(
                        statement_id=f'{owner}.statement.click_or_track_hidden',
                        condition=_has_value(owner, 'image_found', result_symbol, 'optional<image_match>'),
                        then_statements=(
                            _stable_reset(owner, stable, 'reset_hidden_frames'),
                            _assign(
                                owner, 'save_last_match', last_match, '最后匹配',
                                'optional<image_match>',
                                _symbol(owner, 'last_match_source', result_symbol, 'optional<image_match>'),
                                declare=False,
                            ),
                            _click_match(owner, 'click_match_center', result_symbol),
                            _number_change(
                                owner, 'increment_click_count', click_count, '点击次数',
                                'core.number_add.v1',
                            ),
                        ),
                        otherwise_statements=(
                            _stable_increment(owner, stable, 'increment_hidden_frames'),
                            IfStatement(
                                statement_id=f'{owner}.statement.return_when_hidden',
                                condition=_stable_reached(owner, stable, 'hidden_is_stable'),
                                then_statements=(_return(
                                    owner, 'return_hidden_report',
                                    click_report(True, 'hidden_report'),
                                ),),
                            ),
                        ),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_click_loop_timeout', click_report(False, 'timeout_report'))),
            ('official.image.find', 'official.input.click', 'official.wait.duration'),
            ('fresh_check', 'click_each_match_center', 'consecutive_misses', 'monotonic_deadline', 'cancellable'),
        )
    )

    values.append(_click_position_condition_definition(
        'official.image.click_position_until_visible', wait_visible=True,
    ))
    values.append(_click_position_condition_definition(
        'official.image.click_position_until_hidden', wait_visible=False,
    ))

    owner = 'official.text.match'
    ocr_symbol = f'{owner}.symbol.ocr_result'
    text_value = MemberAccessValue(
        value_id=f'{owner}.value.recognized_text',
        source=_symbol(owner, 'ocr_source', ocr_symbol, 'ocr_result'),
        field_id='ocr_result.field.text', result_type='string',
    )
    text_matches = _operation(owner, 'text_matches', 'core.text_matches.v1', 'bool', {
        'actual': text_value,
        'expected': _reference(owner, 'text', 'string', 'target_text'),
        'mode': _reference(owner, 'mode', 'enum<text_match_mode>', 'match_mode'),
    })
    values.append(
        _definition(
            owner, _TEXT_PARAMETERS, 'optional<ocr_result>',
            (
                _call(owner, 'recognize_fresh_frame', 'official.text.recognize', (
                    ('region', 'region', 'optional<rect>'),
                    ('language', 'language', 'enum<ocr_language>'),
                ), result=(ocr_symbol, 'OCR 结果', 'ocr_result')),
                IfStatement(
                    statement_id=f'{owner}.statement.return_if_matched', condition=text_matches,
                    then_statements=(_return(
                        owner, 'return_matched_text',
                        _symbol(owner, 'matched_text_return', ocr_symbol, 'ocr_result'),
                    ),),
                ),
                _return(owner, 'return_text_mismatch', NullValue(
                    value_id=f'{owner}.value.mismatch_null',
                )),
            ),
            ('official.text.recognize',),
            ('fresh_check', 'exact_contains_regex', 'normal_empty_mismatch', 'cancellable'),
        )
    )

    owner = 'official.text.wait_visible'
    setup, remaining = _remaining_setup(owner)
    stable_setup, stable = _stable_setup(owner)
    ocr_symbol = f'{owner}.symbol.ocr_result'
    last_ocr = f'{owner}.symbol.last_ocr_result'
    last_setup = _assign(
        owner, 'initialize_last_ocr', last_ocr, '最后文字结果', 'optional<ocr_result>',
        NullValue(value_id=f'{owner}.value.last_ocr_null'), declare=True,
    )
    text_value = MemberAccessValue(
        value_id=f'{owner}.value.recognized_text',
        source=_symbol(owner, 'ocr_source', ocr_symbol, 'ocr_result'),
        field_id='ocr_result.field.text', result_type='string',
    )
    text_matches = _operation(owner, 'text_matches', 'core.text_matches.v1', 'bool', {
        'actual': text_value,
        'expected': _reference(owner, 'text', 'string', 'target_text'),
        'mode': _reference(owner, 'mode', 'enum<text_match_mode>', 'match_mode'),
    })
    decrement, wait = _wait_if_remaining(owner, remaining, 'text_visible')
    values.append(
        _definition(
            owner,
            _TEXT_PARAMETERS + (('timeout', 'duration'), ('interval', 'duration'), ('stable_frames', 'int64')),
            'optional<ocr_result>',
            (setup, stable_setup, last_setup, LoopStatement(
                statement_id=f'{owner}.statement.poll', mode='while',
                source=_remaining_condition(owner, remaining, 'text_visible.loop'),
                body=(
                    _call(owner, 'recognize_fresh_frame', 'official.text.recognize', (
                        ('region', 'region', 'optional<rect>'),
                        ('language', 'language', 'enum<ocr_language>'),
                    ), result=(ocr_symbol, 'OCR 结果', 'ocr_result')),
                    IfStatement(
                        statement_id=f'{owner}.statement.track_text_stability',
                        condition=text_matches,
                        then_statements=(
                            _stable_increment(owner, stable, 'increment_text_frames'),
                            _assign(
                                owner, 'save_last_ocr', last_ocr, '最后文字结果',
                                'optional<ocr_result>',
                                _symbol(owner, 'last_ocr_source', ocr_symbol, 'ocr_result'),
                                declare=False,
                            ),
                            IfStatement(
                                statement_id=f'{owner}.statement.return_when_stable',
                                condition=_stable_reached(owner, stable, 'text_is_stable'),
                                then_statements=(_return(
                                    owner, 'return_text_result',
                                    _symbol(owner, 'text_result_return', last_ocr, 'optional<ocr_result>'),
                                ),),
                            ),
                        ),
                        otherwise_statements=(
                            _stable_reset(owner, stable, 'reset_text_frames'),
                            _assign(
                                owner, 'clear_last_ocr', last_ocr, '最后文字结果',
                                'optional<ocr_result>',
                                NullValue(value_id=f'{owner}.value.clear_last_ocr.null'),
                                declare=False,
                            ),
                        ),
                    ),
                    decrement, wait,
                ),
            ), _return(owner, 'return_text_timeout', NullValue(
                value_id=f'{owner}.value.timeout_null',
            ))),
            ('official.text.recognize', 'official.wait.duration'),
            ('fresh_check', 'exact_contains_regex', 'consecutive_matches', 'monotonic_deadline', 'normal_empty_timeout', 'cancellable'),
        )
    )
    return {item.function_id: item for item in values}


STANDARD_FUNCTION_DEFINITIONS = _build_definitions()


def require_standard_definition(function_id: str) -> StandardFunctionDefinitionV6:
    try:
        return STANDARD_FUNCTION_DEFINITIONS[function_id]
    except KeyError as exc:
        raise KeyError(f'unknown standard function definition: {function_id}') from exc


def _value(arguments: dict[str, Any], function_id: str, name: str, default: Any = None) -> Any:
    return arguments.get(f'{function_id}.parameter.{name}', default)


def _milliseconds(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeFailure(f'{label}必须是持续时间', error_id='target.invalid_duration')
    milliseconds = float(value)
    if milliseconds < 0 or (positive and milliseconds <= 0):
        raise RuntimeFailure(f'{label}必须{">" if positive else ">="} 0', error_id='target.invalid_duration')
    return milliseconds


def _stable_frames(arguments: dict[str, Any], function_id: str, default: int) -> int:
    value = _value(arguments, function_id, 'stable_frames', default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise RuntimeFailure('稳定帧必须是 1 到 100 的整数', error_id='runtime.argument_range')
    return value


class StandardRuntimeV6:
    """Execute the fused projection of the canonical standard definitions."""

    _OPCODES = frozenset({
        'standard.window.wait_visible',
        'standard.control.wait_visible', 'standard.control.wait_hidden',
        'standard.image.wait_visible', 'standard.image.wait_hidden',
        'standard.image.click_once', 'standard.image.click_until_hidden',
        'standard.image.click_position_until_visible',
        'standard.image.click_position_until_hidden',
        'standard.text.match', 'standard.text.wait_visible',
    })

    @classmethod
    def supports(cls, opcode: str) -> bool:
        return opcode in cls._OPCODES

    @staticmethod
    def _check_cancel(cancelled: Callable[[], bool]) -> None:
        if cancelled():
            raise RuntimeFailure('标准函数已取消', error_id='runtime.cancelled')

    @classmethod
    def _sleep(
        cls,
        deadline: float,
        interval_ms: float,
        cancelled: Callable[[], bool],
        safe_checkpoint: Callable[[], None],
    ) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        target = time.monotonic() + min(remaining, interval_ms / 1000.0)
        while time.monotonic() < target:
            safe_checkpoint()
            cls._check_cancel(cancelled)
            time.sleep(min(0.02, max(0.0, target - time.monotonic())))

    @staticmethod
    def _atomic(
        driver: Any,
        opcode: str,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
    ) -> Any:
        if driver is None or not hasattr(driver, 'supports') or not driver.supports(opcode):
            raise RuntimeFailure(
                f'标准函数依赖的原子能力不可用：{opcode}',
                error_id='target.capability_unsupported',
            )
        result = driver.execute(opcode, arguments, cancelled)
        # Standard functions own their single, user-facing summary. Discard
        # atomic messages here so a later direct call cannot inherit a stale
        # internal polling message.
        consume_message = getattr(driver, 'consume_message', None)
        if callable(consume_message):
            consume_message()
        return result

    @staticmethod
    def _image_diagnostic(driver: Any, match: Any, threshold: float) -> tuple[float | None, float]:
        diagnostic_reader = getattr(driver, 'image_match_diagnostic', None)
        diagnostic = diagnostic_reader() if callable(diagnostic_reader) else {}
        score = diagnostic.get('best_similarity') if isinstance(diagnostic, dict) else None
        actual_threshold = diagnostic.get('threshold') if isinstance(diagnostic, dict) else None
        if not isinstance(score, (int, float)) and isinstance(match, dict):
            score = match.get('image_match.field.similarity')
        return (
            float(score) if isinstance(score, (int, float)) else None,
            float(actual_threshold) if isinstance(actual_threshold, (int, float)) else float(threshold),
        )

    @staticmethod
    def _image_score_text(label: str, score: float | None, threshold: float) -> str:
        rendered = f'{score:.3f}' if score is not None else '不可用'
        return f'{label} {rendered}，阈值 {threshold:.3f}'

    @staticmethod
    def _image_find_arguments(arguments: dict[str, Any], function_id: str) -> dict[str, Any]:
        return {
            'official.image.find.parameter.image': _value(arguments, function_id, 'image'),
            'official.image.find.parameter.similarity': _value(arguments, function_id, 'similarity', 0.85),
            'official.image.find.parameter.region': _value(arguments, function_id, 'region'),
        }

    @staticmethod
    def _ocr_arguments(arguments: dict[str, Any], function_id: str) -> dict[str, Any]:
        return {
            'official.text.recognize.parameter.region': _value(arguments, function_id, 'region'),
            'official.text.recognize.parameter.language': _value(arguments, function_id, 'language', 'auto'),
        }

    @staticmethod
    def _matches(actual: str, expected: str, mode: str) -> bool:
        if not expected:
            raise RuntimeFailure('目标文字不能为空', error_id='runtime.argument_range')
        if mode == 'exact':
            return actual == expected
        if mode == 'contains':
            return expected in actual
        if mode == 'regex':
            try:
                return re.search(expected, actual) is not None
            except re.error as exc:
                raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
        raise RuntimeFailure('文字匹配方式无效', error_id='runtime.argument_range')

    def execute(
        self,
        opcode: str,
        function_id: str,
        arguments: dict[str, Any],
        driver: Any,
        cancelled: Callable[[], bool],
        emit: Callable[[str], None],
        *,
        safe_checkpoint: Callable[[], None],
    ) -> Any:
        if not self.supports(opcode):
            raise RuntimeFailure(f'标准函数运行时不支持：{opcode}', error_id='runtime.operation_unsupported')
        self._check_cancel(cancelled)
        if opcode == 'standard.text.match':
            return self._text_match(function_id, arguments, driver, cancelled, emit)
        timeout_ms = _milliseconds(_value(arguments, function_id, 'timeout', 3000), '超时')
        interval_ms = _milliseconds(_value(arguments, function_id, 'interval', 100), '检查间隔', positive=True)
        deadline = time.monotonic() + timeout_ms / 1000.0
        if opcode == 'standard.window.wait_visible':
            return self._window_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms)
        if opcode == 'standard.control.wait_visible':
            return self._control_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms, visible=True)
        if opcode == 'standard.control.wait_hidden':
            return self._control_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms, visible=False)
        if opcode == 'standard.image.wait_visible':
            return self._image_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms, visible=True)
        if opcode == 'standard.image.wait_hidden':
            return self._image_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms, visible=False)
        if opcode == 'standard.image.click_once':
            match = self._image_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms, visible=True)
            if match is not None:
                self._click(function_id, arguments, driver, cancelled, match)
                emit('图像.点击一次：已点击匹配中心')
            return match
        if opcode == 'standard.image.click_position_until_visible':
            return self._click_position_until_condition(
                function_id, arguments, driver, cancelled, emit, safe_checkpoint,
                deadline, interval_ms, visible=True,
            )
        if opcode == 'standard.image.click_position_until_hidden':
            return self._click_position_until_condition(
                function_id, arguments, driver, cancelled, emit, safe_checkpoint,
                deadline, interval_ms, visible=False,
            )
        if opcode == 'standard.text.wait_visible':
            return self._text_wait(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms)
        return self._click_until_hidden(function_id, arguments, driver, cancelled, emit, safe_checkpoint, deadline, interval_ms)

    def _window_wait(self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval):
        checks = 0
        while True:
            self._check_cancel(cancelled)
            checks += 1
            result = self._atomic(driver, 'window.find', {
                'official.window.find.parameter.selector': _value(arguments, fid, 'selector'),
            }, cancelled)
            if result is not None:
                emit(f'窗口.等待出现：已找到（检查 {checks} 次）')
                return result
            if time.monotonic() >= deadline:
                emit(f'窗口.等待出现：到期未找到（检查 {checks} 次）')
                return None
            self._sleep(deadline, interval, cancelled, checkpoint)

    def _control_wait(self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval, *, visible):
        checks = 0
        while True:
            self._check_cancel(cancelled)
            checks += 1
            result = self._atomic(driver, 'control.find', {
                'official.control.find.parameter.selector': _value(arguments, fid, 'selector'),
            }, cancelled)
            condition = result is not None if visible else result is None
            if condition:
                emit(f'控件.等待{"出现" if visible else "消失"}：已满足（检查 {checks} 次）')
                return result if visible else True
            if time.monotonic() >= deadline:
                emit(f'控件.等待{"出现" if visible else "消失"}：到期（检查 {checks} 次）')
                return None if visible else False
            self._sleep(deadline, interval, cancelled, checkpoint)

    def _image_wait(self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval, *, visible):
        stable_required = _stable_frames(arguments, fid, 1 if visible else 2)
        stable = checks = 0
        last_match = None
        threshold = float(_value(arguments, fid, 'similarity', 0.85))
        last_score = best_score = lowest_score = None
        while True:
            self._check_cancel(cancelled)
            checks += 1
            match = self._atomic(
                driver, 'vision.find', self._image_find_arguments(arguments, fid), cancelled,
            )
            last_score, threshold = self._image_diagnostic(driver, match, threshold)
            if last_score is not None:
                best_score = last_score if best_score is None else max(best_score, last_score)
                lowest_score = last_score if lowest_score is None else min(lowest_score, last_score)
            condition = match is not None if visible else match is None
            stable = stable + 1 if condition else 0
            if match is not None:
                last_match = match
            if stable >= stable_required:
                detail = self._image_score_text('当前相似度', last_score, threshold)
                emit(f'图像.等待{"出现" if visible else "消失"}：稳定 {stable_required} 帧（检查 {checks} 次），{detail}')
                return last_match if visible else True
            if time.monotonic() >= deadline:
                score = best_score if visible else lowest_score
                label = '最高相似度' if visible else '最低相似度'
                detail = self._image_score_text(label, score, threshold)
                emit(f'图像.等待{"出现" if visible else "消失"}：到期（检查 {checks} 次），{detail}')
                return None if visible else False
            self._sleep(deadline, interval, cancelled, checkpoint)

    def _click(self, fid, arguments, driver, cancelled, match) -> None:
        center = match.get('image_match.field.center') if isinstance(match, dict) else None
        if not isinstance(center, dict):
            raise RuntimeFailure('图像匹配结果缺少中心坐标', error_id='runtime.member_missing')
        self._atomic(driver, 'input.click', {
            'official.input.click.parameter.position': center,
            'official.input.click.parameter.button': _value(arguments, fid, 'button', 'primary'),
            'official.input.click.parameter.count': 1,
            'official.input.click.parameter.interval': 0,
        }, cancelled)

    def _click_fixed_position(self, fid, arguments, driver, cancelled) -> None:
        self._atomic(driver, 'input.click', {
            'official.input.click.parameter.position': _value(arguments, fid, 'position'),
            'official.input.click.parameter.button': _value(arguments, fid, 'button', 'primary'),
            'official.input.click.parameter.count': 1,
            'official.input.click.parameter.interval': 0,
        }, cancelled)

    def _click_position_until_condition(
        self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval, *, visible,
    ):
        required = _stable_frames(arguments, fid, 1 if visible else 2)
        stable = clicks = checks = 0
        last_match = None
        threshold = float(_value(arguments, fid, 'similarity', 0.85))
        last_score = best_score = lowest_score = None
        action_name = f'图像.点击位置直到{"出现" if visible else "消失"}'
        while True:
            self._check_cancel(cancelled)
            checks += 1
            match = self._atomic(driver, 'vision.find', self._image_find_arguments(arguments, fid), cancelled)
            last_score, threshold = self._image_diagnostic(driver, match, threshold)
            if last_score is not None:
                best_score = last_score if best_score is None else max(best_score, last_score)
                lowest_score = last_score if lowest_score is None else min(lowest_score, last_score)
            condition = match is not None if visible else match is None
            if condition:
                stable += 1
                if match is not None:
                    last_match = match
                if stable >= required:
                    detail = self._image_score_text('当前相似度', last_score, threshold)
                    emit(f'{action_name}：目标状态已达到，点击 {clicks} 次（检查 {checks} 次），{detail}')
                    return {
                        'image_click_condition_result.field.reached': True,
                        'image_click_condition_result.field.click_count': clicks,
                        'image_click_condition_result.field.last_match': last_match,
                    }
            else:
                stable = 0
                if match is not None:
                    last_match = match
                self._click_fixed_position(fid, arguments, driver, cancelled)
                clicks += 1
            if time.monotonic() >= deadline:
                score = best_score if visible else lowest_score
                label = '最高相似度' if visible else '最低相似度'
                detail = self._image_score_text(label, score, threshold)
                emit(f'{action_name}：到期，点击 {clicks} 次（检查 {checks} 次），{detail}')
                return {
                    'image_click_condition_result.field.reached': False,
                    'image_click_condition_result.field.click_count': clicks,
                    'image_click_condition_result.field.last_match': last_match,
                }
            self._sleep(deadline, interval, cancelled, checkpoint)

    def _click_until_hidden(self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval):
        required = _stable_frames(arguments, fid, 2)
        hidden_frames = clicks = checks = 0
        last_match = None
        threshold = float(_value(arguments, fid, 'similarity', 0.85))
        last_score = lowest_score = None
        while True:
            self._check_cancel(cancelled)
            checks += 1
            match = self._atomic(driver, 'vision.find', self._image_find_arguments(arguments, fid), cancelled)
            last_score, threshold = self._image_diagnostic(driver, match, threshold)
            if last_score is not None:
                lowest_score = last_score if lowest_score is None else min(lowest_score, last_score)
            if match is None:
                hidden_frames += 1
                if hidden_frames >= required:
                    detail = self._image_score_text('当前相似度', last_score, threshold)
                    emit(f'图像.点击直到消失：已消失，点击 {clicks} 次，{detail}')
                    return {
                        'image_click_loop_result.field.hidden': True,
                        'image_click_loop_result.field.click_count': clicks,
                        'image_click_loop_result.field.last_match': last_match,
                    }
            else:
                hidden_frames = 0
                last_match = match
                self._click(fid, arguments, driver, cancelled, match)
                clicks += 1
            if time.monotonic() >= deadline:
                detail = self._image_score_text('最低相似度', lowest_score, threshold)
                emit(f'图像.点击直到消失：到期，点击 {clicks} 次，{detail}')
                return {
                    'image_click_loop_result.field.hidden': False,
                    'image_click_loop_result.field.click_count': clicks,
                    'image_click_loop_result.field.last_match': last_match,
                }
            self._sleep(deadline, interval, cancelled, checkpoint)

    def _text_match(self, fid, arguments, driver, cancelled, emit):
        mode = str(_value(arguments, fid, 'mode', 'contains'))
        expected = str(_value(arguments, fid, 'text', ''))
        if mode == 'regex':
            try:
                re.compile(expected)
            except re.error as exc:
                raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
        result = self._atomic(driver, 'text.recognize', self._ocr_arguments(arguments, fid), cancelled)
        actual = str(result.get('ocr_result.field.text') or '') if isinstance(result, dict) else ''
        matched = self._matches(actual, expected, mode)
        emit(f'文字.匹配：{"命中" if matched else "未命中"}')
        return result if matched else None

    def _text_wait(self, fid, arguments, driver, cancelled, emit, checkpoint, deadline, interval):
        required = _stable_frames(arguments, fid, 1)
        stable = checks = 0
        last_result = None
        mode = str(_value(arguments, fid, 'mode', 'contains'))
        expected = str(_value(arguments, fid, 'text', ''))
        if mode == 'regex':
            try:
                re.compile(expected)
            except re.error as exc:
                raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
        while True:
            self._check_cancel(cancelled)
            checks += 1
            result = self._atomic(driver, 'text.recognize', self._ocr_arguments(arguments, fid), cancelled)
            actual = str(result.get('ocr_result.field.text') or '') if isinstance(result, dict) else ''
            if self._matches(actual, expected, mode):
                stable += 1
                last_result = result
            else:
                stable = 0
                last_result = None
            if stable >= required:
                emit(f'文字.等待出现：稳定 {required} 帧（检查 {checks} 次）')
                return last_result
            if time.monotonic() >= deadline:
                emit(f'文字.等待出现：到期未命中（检查 {checks} 次）')
                return None
            self._sleep(deadline, interval, cancelled, checkpoint)


__all__ = [
    'STANDARD_FUNCTION_DEFINITIONS', 'StandardFunctionDefinitionV6',
    'StandardRuntimeV6', 'require_standard_definition',
]
