from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.vnext.target_service import TargetConfiguration
from core.vnext.window_binding_v2 import (
    WindowBindingResolutionError,
    candidate_at_screen_point,
    captured_binding,
    choose_target_window,
)


def _candidate(hwnd: int, pid: int, *, started: int = 1_000, title: str = '超能世界') -> dict:
    return {
        'hwnd': hwnd,
        'process_id': pid,
        'process_started_at_ms': started,
        'title': title,
        'class_name': 'Chrome_WidgetWin_1',
        'executable_name': 'WeChatAppEx.exe',
        'rect': [0, 0, 450, 840],
        'minimized': False,
    }


def _target(binding: dict | None = None) -> dict:
    value = {
        'target_id': 'target_game',
        'name': '左侧游戏',
        'type': 'windows',
        'window_title': '超能世界',
        'window_match': 'exact',
        'work_area': {'mode': 'client'},
        'allow_physical_fallback': True,
    }
    if binding is not None:
        value['window_binding'] = binding
    return value


def test_captured_instance_disambiguates_identical_titles_without_using_list_order() -> None:
    left = _candidate(101, 1001)
    right = {**_candidate(202, 1002), 'rect': [465, 0, 915, 840]}
    binding = captured_binding(right)

    resolved, method = choose_target_window(_target(binding), [left, right])

    assert resolved['hwnd'] == 202
    assert method == 'captured_instance'


def test_reused_hwnd_is_rejected_and_identical_restart_requires_recapture() -> None:
    original = _candidate(101, 1001, started=1_000)
    binding = captured_binding(original)
    restarted_left = _candidate(101, 2001, started=2_000)
    restarted_right = _candidate(202, 2002, started=2_000)

    with pytest.raises(WindowBindingResolutionError) as captured:
        choose_target_window(_target(binding), [restarted_left, restarted_right])

    assert captured.value.error_id == 'target.window_binding_ambiguous'


def test_restart_recovers_only_when_stable_fingerprint_is_unique() -> None:
    binding = captured_binding(_candidate(101, 1001, started=1_000))
    restarted = _candidate(303, 3003, started=3_000)

    resolved, method = choose_target_window(_target(binding), [restarted])

    assert resolved['hwnd'] == 303
    assert method == 'stable_recovery'


def test_uncaptured_duplicate_title_fails_with_capture_guidance() -> None:
    with pytest.raises(WindowBindingResolutionError) as captured:
        choose_target_window(_target(), [_candidate(101, 1001), _candidate(202, 1002)])

    assert captured.value.error_id == 'target.window_binding_ambiguous'
    assert '捕获按钮' in str(captured.value)


def test_frozen_frame_point_uses_topmost_containing_window() -> None:
    top = {**_candidate(202, 1002), 'rect': [100, 100, 300, 300]}
    bottom = {**_candidate(101, 1001), 'rect': [0, 0, 450, 840]}

    assert candidate_at_screen_point([top, bottom], (150, 150))['hwnd'] == 202


def test_target_contract_requires_captured_binding_to_match_exact_title() -> None:
    binding = captured_binding(_candidate(101, 1001))
    valid = TargetConfiguration.model_validate({
        'targets': [_target(binding)],
        'default_target_id': 'target_game',
    })
    assert valid.targets[0].model_dump(mode='json')['window_binding']['hwnd'] == 101

    invalid = _target(binding)
    invalid['window_match'] = 'contains'
    with pytest.raises(ValidationError):
        TargetConfiguration.model_validate({'targets': [invalid], 'default_target_id': 'target_game'})

