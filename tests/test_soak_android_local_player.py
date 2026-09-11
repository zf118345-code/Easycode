from __future__ import annotations

from collections import deque

from scripts import soak_android_local_player as soak


def _harness() -> soak.Harness:
    harness = object.__new__(soak.Harness)
    harness.package = 'com.easycode.player.debug'
    harness.component = 'com.easycode.player.debug/com.easycode.player.PlayerActivity'
    return harness


def test_exercise_requires_a_new_completed_run(monkeypatch) -> None:
    harness = _harness()
    states = deque([
        {'run_id': 'old', 'status': 'completed'},
        {'run_id': 'old', 'status': 'completed'},
        {'run_id': 'new', 'status': 'running'},
        {'run_id': 'new', 'status': 'completed', 'sequence': 17},
    ])
    commands: list[tuple[str, ...]] = []
    harness.state = lambda: states.popleft()  # type: ignore[method-assign]
    harness.shell = lambda *args, **kwargs: commands.append(args) or ''  # type: ignore[method-assign]
    monkeypatch.setattr(soak.time, 'sleep', lambda _seconds: None)

    result = harness.exercise(540, 2190, 1.0)

    assert result['run_id'] == 'new'
    assert result['status'] == 'completed'
    assert ('input', 'tap', '540', '2190') in commands


def test_sample_parses_android_process_battery_thermal_and_disk() -> None:
    harness = _harness()
    replies = {
        ('pidof', harness.package): '1234\n',
        ('dumpsys', 'meminfo', harness.package): (
            'TOTAL PSS:   180054   TOTAL RSS:   316204   TOTAL SWAP PSS: 70\n'
        ),
        ('dumpsys', 'battery'): '  level: 82\n  voltage: 4210\n  temperature: 307\n',
        ('dumpsys', 'thermalservice'): 'Thermal Status: 1\n',
        ('run-as', harness.package, 'du', '-sk', 'files'): '5120 files\n',
    }
    harness.shell = lambda *args, **kwargs: replies[args]  # type: ignore[method-assign]

    sample = harness.sample(12.5)

    assert sample['pid'] == 1234
    assert sample['pss_bytes'] == 180054 * 1024
    assert sample['rss_bytes'] == 316204 * 1024
    assert sample['private_data_bytes'] == 5120 * 1024
    assert sample['battery_level'] == 82
    assert sample['battery_temperature_c'] == 30.7
    assert sample['thermal_status'] == 1


def test_optional_device_telemetry_does_not_require_vendor_fields() -> None:
    assert soak._optional_max([None, None]) is None
    assert soak._optional_max([None, 31.2, 30.5]) == 31.2
