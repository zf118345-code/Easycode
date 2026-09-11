from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.vnext.schedule_v6 import (
    DispatchAcceptance,
    LocalDispatchRequest,
    ScheduleError,
    ScheduleServiceV6,
    SQLiteLocalDispatchGateway,
    StaticScheduleReferenceResolver,
    VirtualClock,
)

HOST = "host-local"
INSTANCE_A = "instance-a"
INSTANCE_B = "instance-b"
PRODUCT = "product-signed"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.requests: list[LocalDispatchRequest] = []

    def accept(self, request: LocalDispatchRequest) -> DispatchAcceptance:
        self.requests.append(request)
        return DispatchAcceptance(request.dispatch_id, f"run-{request.dispatch_id[-16:]}")


def _resolver() -> StaticScheduleReferenceResolver:
    records = {}
    for instance in (INSTANCE_A, INSTANCE_B):
        for profile in ("profile-a", "profile-b", "profile-c"):
            records[(HOST, instance, PRODUCT, profile)] = {
                "dispatch_scope": "local",
                "host_name": "此电脑",
                "instance_name": instance,
                "product_name": "已签名测试产品",
                "profile_name": profile,
                "release_id": "release-6",
            }
    return StaticScheduleReferenceResolver(records)


def _entry(
    entry_id: str = "entry-a",
    *,
    instance_id: str = INSTANCE_A,
    profile_id: str = "profile-a",
    start_offset_seconds: int = 0,
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "enabled": enabled,
        "host_id": HOST,
        "instance_id": instance_id,
        "product_id": PRODUCT,
        "profile_id": profile_id,
        "start_offset_seconds": start_offset_seconds,
    }


def _interval_plan(
    *,
    schedule_id: str = "schedule-main",
    entries: list[dict[str, object]] | None = None,
    anchor: str = "2026-09-01T08:00:00",
    interval_seconds: int = 60,
    misfire_policy: str = "skip",
    max_lateness_seconds: int = 0,
    overlap_policy: str = "skip",
    dispatch_mode: str = "simultaneous",
) -> dict[str, object]:
    return {
        "schedule_id": schedule_id,
        "name": "本地批量计划",
        "enabled": True,
        "timezone_id": "Asia/Shanghai",
        "trigger": {
            "type": "interval",
            "anchor_local_datetime": anchor,
            "interval_seconds": interval_seconds,
        },
        "misfire_policy": misfire_policy,
        "max_lateness_seconds": max_lateness_seconds,
        "overlap_policy": overlap_policy,
        "dispatch_mode": dispatch_mode,
        "entries": entries or [_entry()],
        "created_by": "local-user",
    }


def _service(
    tmp_path: Path,
    clock: VirtualClock,
    dispatcher: RecordingDispatcher | None = None,
) -> ScheduleServiceV6:
    return ScheduleServiceV6(
        tmp_path / "schedules.sqlite3",
        clock=clock,
        resolver=_resolver(),
        dispatcher=dispatcher,
    )


def test_typed_triggers_revision_and_reference_validation(tmp_path: Path) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    service = _service(tmp_path, clock, RecordingDispatcher())

    once = service.create_plan(
        {
            **_interval_plan(schedule_id="schedule-once"),
            "trigger": {"type": "once", "local_datetime": "2026-09-01T08:05:00"},
        }
    )
    daily = service.create_plan(
        {
            **_interval_plan(schedule_id="schedule-daily"),
            "trigger": {"type": "daily", "local_time": "08:30:00"},
        }
    )
    interval = service.create_plan(_interval_plan())

    assert once["trigger"]["type"] == "once"
    assert once["next_due_at"] == "2026-09-01T00:05:00.000Z"
    assert daily["trigger"] == {"type": "daily", "local_time": "08:30:00"}
    assert interval["revision"] == 1

    changed = service.update_plan(
        interval["schedule_id"],
        1,
        {**_interval_plan(), "name": "修改后的计划"},
    )
    assert changed["revision"] == 2
    assert changed["name"] == "修改后的计划"
    with pytest.raises(ScheduleError) as conflict:
        service.update_plan(
            interval["schedule_id"],
            1,
            _interval_plan(),
        )
    assert conflict.value.error_id == "schedule.revision_conflict"

    with pytest.raises(ScheduleError) as bad_zone:
        service.create_plan(
            {**_interval_plan(schedule_id="schedule-bad-zone"), "timezone_id": "UTC+8"}
        )
    assert bad_zone.value.error_id == "schedule.timezone_invalid"

    with pytest.raises(ScheduleError) as bad_reference:
        service.create_plan(
            {
                **_interval_plan(schedule_id="schedule-bad-reference"),
                "entries": [_entry(profile_id="missing-profile")],
            }
        )
    assert bad_reference.value.error_id == "schedule.reference_unknown"


def test_dst_gap_and_fold_have_one_deterministic_daily_occurrence(tmp_path: Path) -> None:
    dispatcher = RecordingDispatcher()
    spring_clock = VirtualClock("2026-03-07T12:00:00Z")
    spring = _service(tmp_path / "spring", spring_clock, dispatcher)
    spring_plan = spring.create_plan(
        {
            **_interval_plan(schedule_id="schedule-spring"),
            "timezone_id": "America/New_York",
            "trigger": {"type": "daily", "local_time": "02:30:00"},
        }
    )
    # 02:30 does not exist on the spring-forward day, so the first valid
    # instant is 03:00 EDT rather than a silent skip or duplicate.
    assert spring_plan["next_due_at"] == "2026-03-08T07:00:00.000Z"

    fall_clock = VirtualClock("2026-10-31T12:00:00Z")
    fall = _service(tmp_path / "fall", fall_clock, RecordingDispatcher())
    fall_plan = fall.create_plan(
        {
            **_interval_plan(schedule_id="schedule-fall"),
            "timezone_id": "America/New_York",
            "trigger": {"type": "daily", "local_time": "01:30:00"},
        }
    )
    assert fall_plan["next_due_at"] == "2026-11-01T05:30:00.000Z"
    fall_clock.set("2026-11-01T05:30:00Z")
    created = fall.process_due()
    assert len(created) == 1
    assert fall.get_plan("schedule-fall")["next_due_at"] == "2026-11-02T06:30:00.000Z"


def test_clock_rollback_does_not_duplicate_an_already_materialized_due_point(
    tmp_path: Path,
) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    service = _service(tmp_path, clock, RecordingDispatcher())
    service.create_plan(_interval_plan())
    clock.set("2026-09-01T00:01:00Z")
    first = service.process_due()[0]
    dispatch = service.list_dispatches(occurrence_id=first["occurrence_id"])[0]
    service.record_run_status(dispatch["dispatch_id"], dispatch["run_id"], "completed")

    clock.set("2026-09-01T00:00:30Z")
    assert service.process_due() == []
    clock.set("2026-09-01T00:01:00Z")
    assert service.process_due() == []
    clock.set("2026-09-01T00:02:00Z")
    second = service.process_due()
    assert len(second) == 1
    assert second[0]["occurrence_id"] != first["occurrence_id"]
    assert len(service.list_occurrences(schedule_id="schedule-main")) == 2


def test_recovery_collapses_history_and_applies_bounded_misfire_policy(tmp_path: Path) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    dispatcher = RecordingDispatcher()
    service = _service(tmp_path, clock, dispatcher)
    service.create_plan(
        _interval_plan(
            schedule_id="schedule-skip",
            anchor="2026-09-01T08:00:00",
            interval_seconds=60,
            misfire_policy="skip",
        )
    )
    service.create_plan(
        _interval_plan(
            schedule_id="schedule-catch",
            anchor="2026-09-01T08:00:00",
            interval_seconds=60,
            misfire_policy="catch_up_once",
            max_lateness_seconds=40,
        )
    )

    clock.advance(minutes=100, seconds=30)
    created = service.process_due(trigger_source="recovery")
    by_schedule = {item["schedule_id"]: item for item in created}
    assert by_schedule["schedule-skip"]["status"] == "skipped"
    assert by_schedule["schedule-skip"]["collapsed_due_count"] == 100
    assert by_schedule["schedule-skip"]["reason_code"] == "schedule.misfire_skipped"
    assert by_schedule["schedule-catch"]["collapsed_due_count"] == 100
    assert by_schedule["schedule-catch"]["trigger_source"] == "recovery_catch_up"
    assert len(dispatcher.requests) == 1
    accepted = service.list_dispatches(
        occurrence_id=by_schedule["schedule-catch"]["occurrence_id"]
    )[0]
    service.record_run_status(accepted["dispatch_id"], accepted["run_id"], "completed")

    # A restart much later still creates one bounded summary occurrence, not
    # one row or one launch per missed interval.
    clock.advance(hours=2, seconds=20)
    later = service.process_due(trigger_source="recovery")
    catch = next(item for item in later if item["schedule_id"] == "schedule-catch")
    assert catch["status"] == "skipped"
    assert catch["reason_code"] == "schedule.catch_up_window_expired"


def test_overlap_queue_once_and_same_instance_fifo(tmp_path: Path) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    dispatcher = RecordingDispatcher()
    service = _service(tmp_path, clock, dispatcher)
    service.create_plan(
        _interval_plan(
            overlap_policy="queue_once",
            entries=[
                _entry("entry-a", profile_id="profile-a"),
                _entry("entry-b", profile_id="profile-b"),
                _entry("entry-c", instance_id=INSTANCE_B, profile_id="profile-c"),
            ],
        )
    )

    clock.advance(minutes=1)
    first = service.process_due()[0]
    first_dispatches = service.list_dispatches(occurrence_id=first["occurrence_id"])
    accepted = [item for item in first_dispatches if item["status"] == "accepted"]
    queued = [item for item in first_dispatches if item["status"] == "queued"]
    assert len(accepted) == 2  # one FIFO head for each independent instance
    assert len(queued) == 1

    clock.advance(minutes=1)
    second = service.process_due()[0]
    assert second["status"] == "queued_overlap"
    clock.advance(minutes=1)
    third = service.process_due()[0]
    assert third["status"] == "skipped"
    assert third["reason_code"] == "schedule.overlap_queue_already_exists"

    first_a = next(item for item in accepted if item["instance_id"] == INSTANCE_A)
    service.record_run_status(first_a["dispatch_id"], first_a["run_id"], "completed")
    first_dispatches = service.list_dispatches(occurrence_id=first["occurrence_id"])
    second_a = next(item for item in first_dispatches if item["entry_id"] == "entry-b")
    assert second_a["status"] == "accepted"

    # Finish every first occurrence entry.  The single queued overlap is then
    # promoted, while the third occurrence remains a recorded skip.
    for item in service.list_dispatches(occurrence_id=first["occurrence_id"]):
        if item["status"] == "accepted":
            service.record_run_status(item["dispatch_id"], item["run_id"], "completed")
    promoted = service.get_occurrence(second["occurrence_id"])
    assert promoted["status"] in {"accepted", "pending"}
    assert len(service.list_dispatches(occurrence_id=second["occurrence_id"])) == 3


def test_staggered_offsets_do_not_block_other_instances(tmp_path: Path) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    dispatcher = RecordingDispatcher()
    service = _service(tmp_path, clock, dispatcher)
    service.create_plan(
        _interval_plan(
            dispatch_mode="staggered",
            entries=[
                _entry("entry-a", instance_id=INSTANCE_A),
                _entry(
                    "entry-b",
                    instance_id=INSTANCE_B,
                    profile_id="profile-b",
                    start_offset_seconds=15,
                ),
            ],
        )
    )
    clock.advance(minutes=1)
    occurrence = service.process_due()[0]
    rows = service.list_dispatches(occurrence_id=occurrence["occurrence_id"])
    assert {row["status"] for row in rows} == {"accepted", "pending"}
    assert len(dispatcher.requests) == 1
    clock.advance(seconds=15)
    service.pump()
    assert len(dispatcher.requests) == 2

    with pytest.raises(ScheduleError) as invalid:
        service.create_plan(
            _interval_plan(
                schedule_id="schedule-invalid-offset",
                dispatch_mode="simultaneous",
                entries=[_entry(start_offset_seconds=1)],
            )
        )
    assert invalid.value.error_id == "schedule.policy_invalid"


def test_occurrence_snapshot_and_dispatch_ids_survive_restart(tmp_path: Path) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    dispatcher = RecordingDispatcher()
    database = tmp_path / "schedules.sqlite3"
    service = ScheduleServiceV6(
        database,
        clock=clock,
        resolver=_resolver(),
        dispatcher=dispatcher,
    )
    plan = service.create_plan(_interval_plan())
    clock.advance(minutes=1)
    occurrence = service.process_due()[0]
    dispatch = service.list_dispatches(occurrence_id=occurrence["occurrence_id"])[0]

    service.update_plan(
        plan["schedule_id"],
        1,
        {
            **_interval_plan(),
            "entries": [_entry(profile_id="profile-b")],
        },
    )
    assert service.get_occurrence(occurrence["occurrence_id"])["entries"][0]["profile_id"] == "profile-a"

    restarted = ScheduleServiceV6(
        database,
        clock=clock,
        resolver=_resolver(),
        dispatcher=dispatcher,
    )
    assert restarted.get_dispatch(dispatch["dispatch_id"])["run_id"] == dispatch["run_id"]
    assert len(restarted.list_occurrences(schedule_id=plan["schedule_id"])) == 1
    assert len(restarted.list_dispatches(occurrence_id=occurrence["occurrence_id"])) == 1


def test_local_dispatch_gateway_is_idempotent_and_reuses_run_id(tmp_path: Path) -> None:
    starts: list[tuple[str, str]] = []

    def launcher(request: LocalDispatchRequest, run_id: str) -> None:
        starts.append((request.dispatch_id, run_id))

    gateway = SQLiteLocalDispatchGateway(tmp_path / "admissions.sqlite3", launcher)
    request = LocalDispatchRequest(
        dispatch_id="dispatch-stable",
        occurrence_id="occurrence-stable",
        schedule_id="schedule-main",
        schedule_revision=1,
        entry_id="entry-a",
        host_id=HOST,
        instance_id=INSTANCE_A,
        product_id=PRODUCT,
        profile_id="profile-a",
        requested_at="2026-09-01T00:01:00.000Z",
    )
    first = gateway.accept(request)
    second = gateway.accept(request)
    assert first.run_id == second.run_id
    assert starts == [(request.dispatch_id, first.run_id)]

    changed = LocalDispatchRequest(
        **{**request.as_dict(), "profile_id": "profile-b"},
    )
    with pytest.raises(ScheduleError) as conflict:
        gateway.accept(changed)
    assert conflict.value.error_id == "schedule.dispatch_identity_conflict"


def test_local_dispatch_gateway_retry_keeps_the_same_execution_identity(tmp_path: Path) -> None:
    attempted_run_ids: list[str] = []

    def flaky_launcher(_request: LocalDispatchRequest, run_id: str) -> None:
        attempted_run_ids.append(run_id)
        if len(attempted_run_ids) == 1:
            raise ScheduleError(
                "Execution Service 暂时不可用",
                error_id="schedule.execution_start_failed",
                transient=True,
                action="retry",
            )

    gateway = SQLiteLocalDispatchGateway(tmp_path / "admissions.sqlite3", flaky_launcher)
    request = LocalDispatchRequest(
        dispatch_id="dispatch-retry",
        occurrence_id="occurrence-retry",
        schedule_id="schedule-main",
        schedule_revision=1,
        entry_id="entry-a",
        host_id=HOST,
        instance_id=INSTANCE_A,
        product_id=PRODUCT,
        profile_id="profile-a",
        requested_at="2026-09-01T00:01:00.000Z",
    )
    with pytest.raises(ScheduleError) as first:
        gateway.accept(request)
    assert first.value.transient is True
    retry = LocalDispatchRequest(
        **{**request.as_dict(), "requested_at": "2026-09-01T00:01:30.000Z"},
    )
    accepted = gateway.accept(retry)
    assert attempted_run_ids == [accepted.run_id, accepted.run_id]


def test_missing_execution_adapter_is_an_honest_failure_with_safe_diagnostics(
    tmp_path: Path,
) -> None:
    clock = VirtualClock("2026-09-01T00:00:00Z")
    service = _service(tmp_path, clock, dispatcher=None)
    service.create_plan(_interval_plan())
    clock.advance(minutes=1)
    occurrence = service.process_due()[0]
    dispatch = service.list_dispatches(occurrence_id=occurrence["occurrence_id"])[0]
    assert dispatch["status"] == "pending"
    assert dispatch["run_id"] is None
    assert dispatch["error_id"] == "schedule.execution_adapter_unavailable"

    diagnostics = service.list_diagnostics()
    serialized = str(diagnostics).lower()
    assert "profile_values" not in serialized
    assert "authorization" not in serialized
    assert "secret" not in serialized
    assert any(item["event_type"] == "dispatch.failed" for item in diagnostics)


def test_virtual_clock_requires_explicit_utc_offset() -> None:
    with pytest.raises(ScheduleError) as exc:
        VirtualClock(datetime(2026, 9, 1, 0, 0))
    assert exc.value.error_id == "schedule.time_invalid"
    assert (
        VirtualClock(datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)).now().tzinfo
        is timezone.utc
    )
