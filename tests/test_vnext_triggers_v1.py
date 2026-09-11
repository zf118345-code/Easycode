from __future__ import annotations

import time

import pytest

from core.vnext.triggers_v1 import TriggerError, TriggerRuntimeV1, TriggerServiceV1


def _trigger(**changes):
    value = {
        "display_name": "保存后运行",
        "enabled": True,
        "kind": "filesystem",
        "kind_config": {"path": "C:/demo/input.txt"},
        "entry_function_id": "func_main",
        "target_id": "",
        "debounce_ms": 250,
        "cooldown_ms": 1000,
        "concurrency_policy": "skip_if_running",
        "permission_requirements": ["filesystem.read"],
    }
    value.update(changes)
    return value


def test_trigger_configuration_is_revisioned_and_disabled_definitions_are_inert(tmp_path) -> None:
    service = TriggerServiceV1()
    initial = service.configuration(str(tmp_path))
    saved = service.save(str(tmp_path), initial["revision"], _trigger(enabled=False))
    assert saved["revision"] != initial["revision"]
    assert saved["triggers"][0]["enabled"] is False
    with pytest.raises(TriggerError) as conflict:
        service.save(str(tmp_path), initial["revision"], _trigger())
    assert conflict.value.error_id == "trigger.revision_conflict"


def test_event_storm_obeys_cooldown_and_running_policy(tmp_path) -> None:
    started = []
    active = {"run_1": True}

    def callback(trigger):
        started.append(trigger["trigger_id"])
        return {"execution_id": "run_1"}

    runtime = TriggerRuntimeV1(str(tmp_path), callback, lambda execution_id: active.get(execution_id, False))
    trigger = _trigger(trigger_id="trigger_watch", debounce_ms=0)
    runtime.dispatch(trigger, {"change": 1})
    runtime.dispatch(trigger, {"change": 2})
    assert started == ["trigger_watch"]
    assert runtime.events[-1]["status"] in {"skipped_cooldown", "skipped_running"}
    active["run_1"] = False
    runtime._last_fired["trigger_watch"] = int(time.time() * 1000) - 2000
    runtime.dispatch(trigger, {"change": 3})
    assert started == ["trigger_watch", "trigger_watch"]


def test_duplicate_enabled_shortcuts_are_rejected(tmp_path) -> None:
    service = TriggerServiceV1()
    first = service.save(str(tmp_path), service.configuration(str(tmp_path))["revision"], _trigger(
        kind="global_hotkey", kind_config={"shortcut": "Ctrl+Alt+R"}, trigger_id="trigger_one",
    ))
    with pytest.raises(TriggerError) as conflict:
        service.save(str(tmp_path), first["revision"], _trigger(
            kind="global_hotkey", kind_config={"shortcut": "ctrl + alt + r"}, trigger_id="trigger_two",
        ))
    assert conflict.value.error_id == "trigger.shortcut_conflict"


def test_debounce_collapses_repeated_signals(tmp_path) -> None:
    started = []
    runtime = TriggerRuntimeV1(str(tmp_path), lambda trigger: started.append(trigger["trigger_id"]) or {})
    trigger = _trigger(trigger_id="trigger_debounce", debounce_ms=1000, cooldown_ms=0, concurrency_policy="parallel")
    runtime.dispatch(trigger, {"change": 1})
    runtime.dispatch(trigger, {"change": 2})
    assert started == ["trigger_debounce"]
    assert runtime.events[-1]["status"] == "skipped_debounce"


def test_queue_one_keeps_only_latest_pending_signal(tmp_path) -> None:
    started = []
    active = {"run_1": True}

    def callback(trigger):
        started.append(trigger["trigger_id"])
        return {"execution_id": f"run_{len(started)}"}

    runtime = TriggerRuntimeV1(str(tmp_path), callback, lambda execution_id: active.get(execution_id, False))
    trigger = _trigger(trigger_id="trigger_queue", debounce_ms=0, cooldown_ms=0, concurrency_policy="queue_one")
    runtime.dispatch(trigger, {"change": 1})
    runtime.dispatch(trigger, {"change": 2})
    runtime.dispatch(trigger, {"change": 3})
    assert started == ["trigger_queue"]
    assert list(runtime._queued) == ["trigger_queue"]
    active["run_1"] = False
    queued_trigger, evidence = runtime._queued.pop("trigger_queue")
    runtime._active.pop("trigger_queue", None)
    runtime.dispatch(queued_trigger, evidence)
    assert started == ["trigger_queue", "trigger_queue"]
