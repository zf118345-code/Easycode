from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from core.vnext.runtime import RuntimeFailure, VNextRuntime


def _instruction(instruction_id: str, opcode: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        'instruction_id': instruction_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': None,
        'source': {},
        'capabilities': [],
    }


def _ecir(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'entry_function_id': 'function.main',
        'project_variables': [{
            'variable_id': 'enabled',
            'display_name': '启用',
            'value_type': 'bool',
            'default_value': False,
            'constraints': {},
        }],
        'functions': [{
            'function_id': 'function.main',
            'name': '主程序',
            'parameters': [],
            'parameter_definitions': [],
            'return_type': 'null',
            'instructions': instructions,
        }],
    }


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = runtime.snapshot(execution_id)
        if result['status'] in {'completed', 'failed', 'cancelled'}:
            return result
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


def _ref(symbol_id: str, scope: str = 'local') -> dict[str, Any]:
    key = 'variable_id' if scope == 'project' else 'symbol_id'
    return {'kind': 'reference', 'scope': scope, key: symbol_id}


def _log(instruction_id: str, value: Any) -> dict[str, Any]:
    return _instruction(instruction_id, 'log.write', {
        'official.log.output.parameter.content': value,
        'official.log.output.parameter.level': 'info',
        'official.log.output.parameter.category': 'test',
    })


def _operation(operation_id: str, result_type: str, **inputs: Any) -> dict[str, Any]:
    return {
        'kind': 'operation',
        'operation_id': operation_id,
        'result_type': result_type,
        'inputs': {
            f'{operation_id}.input.{name}': value
            for name, value in inputs.items()
        },
    }


def test_application_lifecycle_opcodes_are_dispatched_to_platform_runtime(monkeypatch) -> None:
    calls: list[str] = []

    class FakePlatformRuntime:
        def execute(self, opcode, _function_id, _arguments, _driver, _cancelled, _log, **_kwargs):
            calls.append(opcode)
            return opcode == 'host.app.stop'

    monkeypatch.setattr(
        'core.vnext.platform_runtime_v6.PlatformRuntimeV6',
        FakePlatformRuntime,
    )
    running = _instruction('application.running', 'host.app.is_running', {
        'official.application.is_running.parameter.process': {'kind': 'json', 'value': {'run': 'test'}},
    })
    running['function_id'] = 'official.application.is_running'
    running['result_slot'] = 'running'
    stopped = _instruction('application.stop', 'host.app.stop', {
        'official.application.stop.parameter.process': {'kind': 'json', 'value': {'run': 'test'}},
        'official.application.stop.parameter.timeout': {'kind': 'duration', 'milliseconds': 100},
    })
    stopped['function_id'] = 'official.application.stop'
    stopped['result_slot'] = 'stopped'

    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([running, stopped]))['execution_id'])

    assert result['status'] == 'completed'
    assert calls == ['host.app.is_running', 'host.app.stop']
    assert result['variables'] == {'running': False, 'stopped': True}


def test_assignments_conditions_and_fixed_snapshot_loops_execute() -> None:
    numbers = {'kind': 'list', 'items': [1, 2], 'item_type': 'int64'}
    instructions = [
        _instruction('assign.local', 'data.assign_local', {
            'target': {'symbol_id': 'numbers'}, 'value': numbers,
        }),
        _instruction('assign.project', 'data.assign_project', {
            'target': {'variable_id': 'enabled'}, 'value': True,
        }),
        _instruction('loop.list', 'control.for_each', {
            'source': _ref('numbers'), 'snapshot': True,
            'bindings': {
                'item': {'symbol_id': 'item'}, 'index': {'symbol_id': 'index'},
            },
            'body': [_log('log.item', _ref('item'))],
        }),
        _instruction('if.branches', 'control.if', {
            'condition': False,
            'then': [_log('log.never', 'never')],
            'additional_branches': [{
                'branch_id': 'branch.second',
                'condition': _ref('enabled', 'project'),
                'body': [_log('log.branch', 'elseif')],
            }],
            'otherwise': [_log('log.otherwise', 'otherwise')],
        }),
    ]
    runtime = VNextRuntime(persist_event_log=False)
    execution_id = runtime.start(_ecir(instructions))['execution_id']
    result = _terminal(runtime, execution_id)
    assert result['status'] == 'completed'
    script_events = [item for item in result['events'] if item['category'] == 'test']
    assert [(item['message'], item['instruction_id']) for item in script_events] == [
        ('1', 'log.item'), ('2', 'log.item'), ('elseif', 'log.branch'),
    ]


def test_if_executes_only_the_first_matching_branch() -> None:
    instruction = _instruction('if.first-match', 'control.if', {
        'condition': True,
        'then': [_log('log.first', 'first')],
        'additional_branches': [{
            'branch_id': 'branch.also-true',
            'condition': True,
            'body': [_log('log.second', 'second')],
        }],
        'otherwise': [_log('log.otherwise', 'otherwise')],
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([instruction]))['execution_id'])
    assert result['status'] == 'completed'
    assert [item['message'] for item in result['events'] if item['category'] == 'test'] == ['first']


def test_wait_until_uses_stable_parameter_ids_and_structured_time_value() -> None:
    instruction = _instruction('wait.until', 'wait.until', {
        'official.wait.until.parameter.time': {
            'kind': 'time',
            'value': '00:00:00',
        },
        'official.wait.until.parameter.past_policy': 'immediate',
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(
        runtime,
        runtime.start(_ecir([instruction]))['execution_id'],
    )
    assert result['status'] == 'completed'
    assert any(
        item['instruction_id'] == 'wait.until' and item['message'].startswith('等待到 ')
        for item in result['events']
    )


def test_random_integer_uses_inclusive_bounds_and_rejects_reversed_range() -> None:
    exact = _instruction('random.exact', 'random.integer', {
        'official.random.integer.parameter.minimum': 7,
        'official.random.integer.parameter.maximum': 7,
    })
    exact['result_slot'] = 'random_result'
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([exact]))['execution_id'])
    assert result['status'] == 'completed'
    assert result['variables']['random_result'] == 7

    invalid = _instruction('random.invalid', 'random.integer', {
        'official.random.integer.parameter.minimum': 2,
        'official.random.integer.parameter.maximum': 1,
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([invalid]))['execution_id'])
    assert result['status'] == 'failed'
    assert result['error_id'] == 'random.range_invalid'
    assert result['current_instruction_id'] == 'random.invalid'


def test_time_now_returns_an_aware_iso_value_and_rejects_unknown_timezone() -> None:
    current = _instruction('time.utc', 'time.now', {
        'official.time.now.parameter.timezone': 'UTC',
    })
    current['result_slot'] = 'current_time'
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([current]))['execution_id'])
    assert result['status'] == 'completed'
    parsed = datetime.fromisoformat(result['variables']['current_time'])
    assert parsed.utcoffset() == timedelta(0)

    invalid = _instruction('time.invalid', 'time.now', {
        'official.time.now.parameter.timezone': 'EasyCode/Not-A-Timezone',
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([invalid]))['execution_id'])
    assert result['status'] == 'failed'
    assert result['error_id'] == 'time.timezone_invalid'


def test_time_today_uses_requested_iana_timezone_and_rejects_unknown_timezone(
    monkeypatch,
) -> None:
    fixed = datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.astimezone(tz)

    monkeypatch.setattr('core.vnext.runtime.datetime', FixedDateTime)
    instructions = []
    for suffix, timezone_name in (('utc', 'UTC'), ('shanghai', 'Asia/Shanghai')):
        instruction = _instruction(f'today.{suffix}', 'time.today', {
            'official.time.today.parameter.timezone': timezone_name,
        })
        instruction['result_slot'] = f'today_{suffix}'
        instructions.append(instruction)
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir(instructions))['execution_id'])
    assert result['status'] == 'completed'
    assert result['variables']['today_utc'] == '2026-01-01'
    assert result['variables']['today_shanghai'] == '2026-01-02'

    invalid = _instruction('today.invalid', 'time.today', {
        'official.time.today.parameter.timezone': 'EasyCode/Not-A-Timezone',
    })
    result = _terminal(
        runtime, runtime.start(_ecir([invalid]))['execution_id'],
    )
    assert result['status'] == 'failed'
    assert result['error_id'] == 'time.timezone_invalid'


def test_project_data_directory_is_host_owned_and_never_grants_recursive_delete(
    tmp_path,
) -> None:
    instruction = _instruction(
        'project.data', 'project.data_directory', {},
    )
    instruction['result_slot'] = 'project_data'
    plan = _ecir([instruction])
    plan['project_path'] = str(tmp_path / 'project')
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'completed'
    reference = result['variables']['project_data']
    expected = (tmp_path / 'project' / '.easycode' / 'data').resolve()
    assert reference['kind'] == 'directory_ref'
    assert reference['path'] == str(expected)
    assert expected.is_dir()
    assert {'read', 'list', 'create', 'delete_empty'} <= set(reference['access'])
    assert 'delete_tree' not in reference['access']

    player_data = (tmp_path / 'player-data').resolve()
    player_plan = _ecir([instruction])
    player_plan['runtime_data_directory'] = str(player_data)
    result = _terminal(runtime, runtime.start(player_plan)['execution_id'])
    assert result['status'] == 'completed'
    assert result['variables']['project_data']['path'] == str(player_data)


def test_map_record_json_member_operations_and_map_loop_execute() -> None:
    record = {
        'kind': 'record',
        'record_type': 'record<settings>',
        'fields': {
            'field.total': {
                'kind': 'operation',
                'operation_id': 'core.number_add.v1',
                'inputs': {
                    'core.number_add.v1.input.left': 1,
                    'core.number_add.v1.input.right': 2,
                },
            },
            'field.json': {'kind': 'json', 'value': {'ready': True}},
        },
    }
    mapping = {
        'kind': 'map', 'duplicate_policy': 'error',
        'entries': [{'key': 'a', 'value': 1}, {'key': 'b', 'value': 2}],
    }
    instructions = [
        _instruction('assign.record', 'data.assign_local', {
            'target': {'symbol_id': 'settings'}, 'value': record,
        }),
        _log('log.member', {
            'kind': 'member_access', 'source': _ref('settings'), 'field_id': 'field.total',
        }),
        _instruction('loop.map', 'control.for_each_map', {
            'source': mapping, 'snapshot': True,
            'bindings': {
                'key': {'symbol_id': 'key'}, 'value': {'symbol_id': 'value'},
                'index': {'symbol_id': 'index'},
            },
            'body': [_log('log.map.value', _ref('value'))],
        }),
    ]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir(instructions))['execution_id'])
    assert result['status'] == 'completed'
    assert [
        item['message'] for item in result['events'] if item['category'] == 'test'
    ] == ['3', '1', '2']


def test_strict_optional_member_access_fails_at_the_consuming_instruction() -> None:
    instructions = [
        _instruction('assign.empty-match', 'data.assign_local', {
            'target': {'symbol_id': 'match'}, 'value': None,
        }),
        _log('click.with-required-center', {
            'kind': 'member_access',
            'source': _ref('match'),
            'field_id': 'image_match.field.center',
            'result_type': 'point',
        }),
        _log('must.not.run', '后续副作用不应执行'),
    ]
    runtime = VNextRuntime(persist_event_log=False)

    result = _terminal(runtime, runtime.start(_ecir(instructions))['execution_id'])

    assert result['status'] == 'failed'
    assert result['error_id'] == 'runtime.optional_empty'
    assert '请先判断“有结果”' in result['error']
    assert result['current_instruction_id'] == 'click.with-required-center'
    assert all(item['instruction_id'] != 'must.not.run' for item in result['events'])


def test_value_conversion_text_and_geometry_operations_are_deterministic() -> None:
    instructions = [
        _instruction('assign.boolean-text', 'data.assign_local', {
            'target': {'symbol_id': 'boolean_text'},
            'value': _operation('core.value_to_text.v1', 'string', value=True),
        }),
        _instruction('assign.number-text', 'data.assign_local', {
            'target': {'symbol_id': 'number_text'},
            'value': _operation('core.value_to_text.v1', 'string', value=1e20),
        }),
        _instruction('assign.duration-text', 'data.assign_local', {
            'target': {'symbol_id': 'duration_text'},
            'value': _operation(
                'core.value_to_text.v1', 'string',
                value={'kind': 'duration', 'milliseconds': 2500},
            ),
        }),
        _instruction('assign.dynamic-duration', 'data.assign_local', {
            'target': {'symbol_id': 'dynamic_duration'},
            'value': _operation('core.duration_from_seconds.v1', 'duration', amount=2.5),
        }),
        _instruction('assign.integer', 'data.assign_local', {
            'target': {'symbol_id': 'integer'},
            'value': _operation('core.text_to_int.v1', 'optional<int64>', text='  -42  '),
        }),
        _instruction('assign.invalid-number', 'data.assign_local', {
            'target': {'symbol_id': 'invalid_number'},
            'value': _operation('core.text_to_float.v1', 'optional<float64>', text='12px'),
        }),
        _instruction('assign.nonportable-number', 'data.assign_local', {
            'target': {'symbol_id': 'nonportable_number'},
            'value': _operation('core.text_to_float.v1', 'optional<float64>', text='1_000'),
        }),
        _instruction('assign.unicode-integer', 'data.assign_local', {
            'target': {'symbol_id': 'unicode_integer'},
            'value': _operation('core.text_to_int.v1', 'optional<int64>', text='１２'),
        }),
        _instruction('assign.parts', 'data.assign_local', {
            'target': {'symbol_id': 'parts'},
            'value': _operation('core.text_split.v1', 'list<string>', text='a||b|', separator='|'),
        }),
        _instruction('assign.joined', 'data.assign_local', {
            'target': {'symbol_id': 'joined'},
            'value': _operation(
                'core.text_join.v1', 'string',
                list={'kind': 'list', 'items': ['a', '', 'b', ''], 'item_type': 'string'},
                separator='|',
            ),
        }),
        _instruction('assign.point', 'data.assign_local', {
            'target': {'symbol_id': 'point'},
            'value': _operation(
                'core.point_scale.v1', 'point',
                point={'kind': 'point', 'x': 10, 'y': 5, 'target_id': 'target.fixture', 'space_version': 'v1'},
                scale_x=1.5, scale_y=2,
            ),
        }),
        _instruction('assign.rect', 'data.assign_local', {
            'target': {'symbol_id': 'rect'},
            'value': _operation(
                'core.rect_scale.v1', 'rect',
                rect={
                    'kind': 'rect', 'x': 2, 'y': 3, 'width': 20, 'height': 10,
                    'target_id': 'target.fixture', 'space_version': 'v1',
                },
                scale_x=2, scale_y=0.5,
            ),
        }),
        _instruction('assign.centered-rect', 'data.assign_local', {
            'target': {'symbol_id': 'centered_rect'},
            'value': _operation(
                'core.rect_from_center.v1', 'rect',
                center={'kind': 'point', 'x': 100, 'y': 80},
                width=40, height=20,
            ),
        }),
    ]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir(instructions))['execution_id'])

    assert result['status'] == 'completed'
    assert result['variables']['boolean_text'] == 'true'
    assert result['variables']['number_text'] == '100000000000000000000'
    assert result['variables']['duration_text'] == '2500'
    assert result['variables']['dynamic_duration'] == 2500
    assert result['variables']['integer'] == -42
    assert result['variables']['invalid_number'] is None
    assert result['variables']['nonportable_number'] is None
    assert result['variables']['unicode_integer'] is None
    assert result['variables']['parts'] == ['a', '', 'b', '']
    assert result['variables']['joined'] == 'a||b|'
    assert result['variables']['point'] == {
        'kind': 'point', 'x': 15.0, 'y': 10,
        'target_id': 'target.fixture', 'space_version': 'v1',
    }
    assert result['variables']['rect'] == {
        'kind': 'rect', 'x': 4, 'y': 1.5, 'width': 40, 'height': 5.0,
        'target_id': 'target.fixture', 'space_version': 'v1',
    }
    assert result['variables']['centered_rect'] == {
        'kind': 'rect', 'x': 80.0, 'y': 70.0, 'width': 40, 'height': 20,
    }


def test_text_extraction_and_temporal_operations_are_portable() -> None:
    assignments = {
        'first': _operation('core.text_extract_first_int.v1', 'optional<int64>', text='体力 -86 / 120'),
        'group': _operation(
            'core.text_regex_extract.v1', 'optional<string>',
            text='房间码 215', pattern=r'房间码\s+([0-9]+)', group=1,
        ),
        'groups': _operation(
            'core.text_regex_groups.v1', 'list<string>',
            text='2026-09-04', pattern=r'([0-9]{4})-([0-9]{2})-([0-9]{2})',
        ),
        'parsed': _operation(
            'core.text_parse_datetime.v1', 'optional<datetime>',
            text='2026-09-04 08:30:15', pattern='yyyy-MM-dd HH:mm:ss',
        ),
        'added': _operation(
            'core.datetime_add_duration.v1', 'datetime',
            datetime={'kind': 'datetime', 'value': '2026-09-04T08:30:00+08:00'},
            duration={'kind': 'duration', 'milliseconds': 90_000},
        ),
        'difference': _operation(
            'core.datetime_difference.v1', 'duration',
            later={'kind': 'datetime', 'value': '2026-09-04T08:31:30+08:00'},
            earlier={'kind': 'datetime', 'value': '2026-09-04T08:30:00+08:00'},
        ),
        'formatted': _operation(
            'core.datetime_format.v1', 'string',
            datetime={'kind': 'datetime', 'value': '2026-09-04T08:30:15.123+08:00'},
            pattern='yyyy/MM/dd HH:mm:ss.SSS XXX',
        ),
        'date': _operation('core.date_add_days.v1', 'date', date={'kind': 'date', 'value': '2026-09-04'}, days=-5),
        'days': _operation(
            'core.date_difference.v1', 'int64',
            later={'kind': 'date', 'value': '2026-09-04'}, earlier={'kind': 'date', 'value': '2026-09-01'},
        ),
        'clock': _operation(
            'core.time_add_duration.v1', 'time',
            time={'kind': 'time', 'value': '23:59:30'}, duration={'kind': 'duration', 'milliseconds': 90_000},
        ),
    }
    instructions = [
        _instruction(f'assign.{name}', 'data.assign_local', {
            'target': {'symbol_id': name}, 'value': value,
        })
        for name, value in assignments.items()
    ]
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir(instructions))['execution_id'])
    assert result['status'] == 'completed'
    expected = {
        'first': -86,
        'group': '215',
        'groups': ['2026', '09', '04'],
        'parsed': '2026-09-04T08:30:15',
        'added': '2026-09-04T08:31:30+08:00',
        'difference': 90_000,
        'formatted': '2026/09/04 08:30:15.123 +08:00',
        'date': '2026-08-30',
        'days': 3,
        'clock': '00:01:00',
    }
    assert {key: result['variables'][key] for key in expected} == expected


def test_text_extraction_reports_invalid_regex_and_mixed_timezone() -> None:
    invalid_regex = _instruction('assign.regex', 'data.assign_local', {
        'target': {'symbol_id': 'value'},
        'value': _operation('core.text_regex_extract.v1', 'optional<string>', text='x', pattern='[', group=0),
    })
    mixed_zone = _instruction('assign.time', 'data.assign_local', {
        'target': {'symbol_id': 'value'},
        'value': _operation(
            'core.datetime_difference.v1', 'duration',
            later={'kind': 'datetime', 'value': '2026-09-04T08:30:00+08:00'},
            earlier={'kind': 'datetime', 'value': '2026-09-04T08:30:00'},
        ),
    })
    for instruction, error_id in ((invalid_regex, 'text.regex_invalid'), (mixed_zone, 'time.timezone_mismatch')):
        runtime = VNextRuntime(persist_event_log=False)
        result = _terminal(runtime, runtime.start(_ecir([instruction]))['execution_id'])
        assert result['status'] == 'failed'
        assert result['error_id'] == error_id


def test_color_comparison_is_portable_and_rejects_invalid_channels() -> None:
    color = lambda red, green, blue, alpha=255: {
        'color.field.red': red, 'color.field.green': green,
        'color.field.blue': blue, 'color.field.alpha': alpha,
    }
    operation = _operation(
        'core.color_matches.v1', 'bool',
        actual=color(10, 20, 30), expected=color(12, 18, 31), tolerance=2,
    )
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([
        _instruction('assign.color', 'data.assign_local', {
            'target': {'symbol_id': 'matched'}, 'value': operation,
        }),
    ]))['execution_id'])
    assert result['status'] == 'completed'
    assert result['variables']['matched'] is True

    invalid = _operation(
        'core.color_matches.v1', 'bool',
        actual=color(10, 20, 300), expected=color(10, 20, 30), tolerance=0,
    )
    failed = _terminal(runtime, runtime.start(_ecir([
        _instruction('assign.invalid-color', 'data.assign_local', {
            'target': {'symbol_id': 'matched'}, 'value': invalid,
        }),
    ]))['execution_id'])
    assert failed['status'] == 'failed'
    assert failed['error_id'] == 'runtime.color_invalid'


class _TransientDriver:
    def __init__(self) -> None:
        self.attempts = 0

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode == 'test.transient'

    def execute(self, opcode: str, arguments: dict[str, Any], cancelled) -> None:
        self.attempts += 1
        if self.attempts < 3:
            raise RuntimeFailure('暂时失败', error_id='target.busy', transient=True)


def test_try_retry_catch_finally_and_return_have_structured_semantics() -> None:
    driver = _TransientDriver()
    tried = _instruction('try.retry', 'control.try', {
        'body': [_instruction('driver.call', 'test.transient', {})],
        'retry_policy': {
            'max_retries': 2, 'interval': {'kind': 'duration', 'milliseconds': 0},
            'transient_only': True,
        },
        'catches': [],
        'finally': [_log('log.finally', 'finally')],
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([tried]), driver=driver)['execution_id'])
    assert result['status'] == 'completed'
    assert driver.attempts == 3
    assert any(item['instruction_id'] == 'log.finally' for item in result['events'])
    retry_events = [item for item in result['events'] if '重试' in item['message']]
    assert [item['instruction_id'] for item in retry_events] == ['try.retry', 'try.retry']

    caught = _instruction('try.catch', 'control.try', {
        'body': [_instruction('unsupported.target', 'control.target_scope', {})],
        'retry_policy': None,
        'catches': [{
            'catch_id': 'catch.target',
            'error_ids': ['target.reference_invalid'],
            'error_slot': 'error',
            'body': [_log('log.caught', {
                'kind': 'member_access', 'source': _ref('error'), 'field_id': 'error_id',
            })],
        }],
        'finally': [_log('log.catch.finally', 'done')],
    })
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(_ecir([caught]))['execution_id'])
    assert result['status'] == 'completed'
    assert any(
        item['message'] == 'target.reference_invalid'
        and item['instruction_id'] == 'log.caught'
        for item in result['events']
    )


def test_invalid_target_scope_and_listener_contract_fail_with_stable_diagnostics() -> None:
    for opcode, expected, message_context in (
        ('control.target_scope', 'target.reference_invalid', None),
        ('control.listen', 'runtime.listener_contract_invalid', {'configured': True}),
    ):
        runtime = VNextRuntime(persist_event_log=False)
        result = _terminal(runtime, runtime.start(_ecir([
            _instruction(f'instruction.{opcode}', opcode, {}),
        ]), message_context=message_context)['execution_id'])
        assert result['status'] == 'failed'
        assert result['error_id'] == expected
        assert any(
            item['level'] == 'error'
            and item['instruction_id'] == f'instruction.{opcode}'
            for item in result['events']
        )
