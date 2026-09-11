from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_schedule_hub_router import create_vnext_schedule_hub_router
from api.routers.vnext_schedule_router import create_vnext_schedule_router
from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore
from core.vnext.distribution import VNextDistributionAssembler
from core.vnext.publish import VNextPublisher
from core.vnext.pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash
from core.vnext.schedule_hub_v6 import PlayerHubV6, WindowsTaskSchedulerBridge
from core.vnext.schedule_v6 import LocalDispatchRequest, ScheduleError, SQLiteLocalDispatchGateway
from core.vnext.target_service import TargetConfiguration, target_configuration_revision


def _distribution(
    tmp_path: Path, *, signing_keys: Path | None = None, function_name: str = "主程序",
) -> Path:
    project = tmp_path / "project"
    (project / "assets").mkdir(parents=True)
    (project / "assets" / "registry.json").write_text(
        json.dumps({
            "schema_version": 1,
            "assets": {},
            "folders": {"image": [], "ocr": [], "page": []},
        }) + "\n",
        encoding="utf-8",
    )
    (project / "easycode.lock").write_text(json.dumps({
        "lock_version": 1,
        "project_format": 6,
        "toolchain": {
            "compiler_version": "6.0.0",
            "program_schema": 1,
            "ecir": 1,
            "pure_value_registry_version": PURE_OPERATION_REGISTRY_VERSION,
            "pure_value_registry_sha256": pure_operation_registry_hash(),
        },
        "official_functions": [],
        "extensions": [],
    }) + "\n", encoding="utf-8")
    publisher = VNextPublisher(
        str(project), signing_key_store=AuthorSigningKeyStore(signing_keys or (tmp_path / "keys"))
    )
    linked = {
        "diagnostics": [],
        "ecir": {
            "entry_function_id": "function_main",
            "functions": [{
                "function_id": "function_main",
                "name": function_name,
                "parameters": [],
                "parameter_definitions": [],
                "return_type": "null",
                "instructions": [],
            }],
            "project_variables": [],
            "required_capabilities": [],
            "supported_platforms": ["no_target"],
        },
    }
    form = {"schema_version": 3, "title": "运行", "pages": []}
    target = TargetConfiguration(schema_version=1, targets=[], default_target_id=None)
    project_doc = {
        "project_id": "product_schedule_hub",
        "name": "计划 Hub 固定样例",
        "targets_schema_version": 1,
        "targets": [],
        "default_target_id": None,
        "target_configuration_revision": target_configuration_revision(target),
    }
    report = publisher.report(linked, form)
    published = publisher.build(linked, form, project_doc, report)
    runtime, web = tmp_path / "runtime", tmp_path / "web"
    runtime.mkdir(); web.mkdir()
    (runtime / "EasycodePlayer.exe").write_bytes(b"safe fixed test runtime boundary")
    (runtime / "EasycodeUpdateHelper.exe").write_bytes(b"safe fixed update helper boundary")
    (web / "player.html").write_text("<main>Player</main>", encoding="utf-8")
    (web / "capture.html").write_text("<main>Capture</main>", encoding="utf-8")
    (web / "console.html").write_text("<main>Console</main>", encoding="utf-8")
    assembled = VNextDistributionAssembler(runtime, web).assemble(
        published["path"], tmp_path / "delivery"
    )
    return Path(assembled["path"])


def _profile(hub: PlayerHubV6, installation: dict) -> dict:
    instance = installation["instances"][0]
    raw_installation = hub.registry._installation(installation["installation_id"])
    raw_instance = hub.registry._instance(instance["instance_id"])
    manager = hub.registry._manager(raw_instance, raw_installation)
    return manager.save_profile("", "默认方案", None, {})["profile"]


def test_uninstall_disables_exact_distribution_but_preserves_registry_history(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        distribution = _distribution(tmp_path)
        installation = hub.registry.register_distribution(distribution)
        instance_id = installation["instances"][0]["instance_id"]

        result = hub.registry.disable_distribution(distribution)

        assert result == {
            "disabled": True,
            "installation_id": installation["installation_id"],
            "product_id": installation["product_id"],
            "root_path": str(distribution.resolve()),
        }
        retained = hub.registry.get_installation(installation["installation_id"], include_profiles=True)
        assert retained["enabled"] is False
        assert retained["instances"][0]["instance_id"] == instance_id
        assert retained["instances"][0]["enabled"] is False
        assert hub.registry.disable_distribution(tmp_path / "never-installed") == {
            "disabled": False,
            "reason": "not_registered",
            "root_path": str((tmp_path / "never-installed").resolve()),
        }
    finally:
        hub.shutdown()


def test_registering_an_upgrade_reuses_the_stable_installation_and_instances(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        signing_keys = tmp_path / "author-keys"
        installed_root = _distribution(tmp_path / "release-1", signing_keys=signing_keys)
        first = hub.registry.register_distribution(installed_root)
        first_instance = first["instances"][0]

        replacement = _distribution(
            tmp_path / "release-2", signing_keys=signing_keys, function_name="升级后的主程序",
        )
        shutil.rmtree(installed_root)
        shutil.copytree(replacement, installed_root)
        upgraded = hub.registry.register_distribution(installed_root)

        assert upgraded["installation_id"] == first["installation_id"]
        assert upgraded["release_id"] != first["release_id"]
        assert upgraded["root_path"] == str(installed_root.resolve())
        assert len(hub.registry.list_installations(include_profiles=True)) == 1
        assert upgraded["instances"][0]["instance_id"] == first_instance["instance_id"]
        assert upgraded["instances"][0]["data_root"] == first_instance["data_root"]
        assert upgraded["instances"][0]["installation_id"] == upgraded["installation_id"]
    finally:
        hub.shutdown()


def test_opening_instances_uses_race_free_ports_and_isolated_data_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    hub = PlayerHubV6(tmp_path / 'hub')
    launched: list[tuple[list[str], dict[str, str]]] = []

    class Process:
        pid = 4321

    def fake_popen(arguments, **kwargs):
        launched.append((list(arguments), dict(kwargs['env'])))
        return Process()

    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    try:
        installation = hub.registry.register_distribution(_distribution(tmp_path))
        first = installation['instances'][0]
        second = hub.registry.create_instance(
            installation['installation_id'], name='实例 2',
        )
        hub.registry.launch_instance_player(first['instance_id'])
        hub.registry.launch_instance_player(second['instance_id'])
    finally:
        hub.shutdown()

    assert len(launched) == 2
    assert all(args[args.index('--port') + 1] == '0' for args, _env in launched)
    assert launched[0][1]['EASYCODE_PLAYER_DATA_DIR'] != launched[1][1]['EASYCODE_PLAYER_DATA_DIR']
    assert launched[0][1]['EASYCODE_PLAYER_INSTANCE_ID'] != launched[1][1]['EASYCODE_PLAYER_INSTANCE_ID']


def test_instance_direct_create_uses_lowest_unique_name_and_delete_quarantines_data(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        installation = hub.registry.register_distribution(_distribution(tmp_path))
        second = hub.registry.create_instance(installation["installation_id"])
        third = hub.registry.create_instance(installation["installation_id"])
        assert [second["display_name"], third["display_name"]] == ["实例 2", "实例 3"]
        data_root = Path(second["data_root"])
        (data_root / "profile-marker.txt").write_text("recoverable", encoding="utf-8")

        deleted = hub.registry.delete_instance(
            second["instance_id"], expected_revision=second["revision"],
        )
        recovery = Path(deleted["recovery_path"])
        assert recovery.is_dir()
        assert (recovery / "profile-marker.txt").read_text(encoding="utf-8") == "recoverable"
        assert not data_root.exists()
        with pytest.raises(ScheduleError) as missing:
            hub.registry.get_instance(second["instance_id"])
        assert missing.value.error_id == "schedule.instance_not_found"

        replacement = hub.registry.create_instance(installation["installation_id"])
        assert replacement["display_name"] == "实例 2"
    finally:
        hub.shutdown()


def test_signed_registry_to_hub_to_ordinary_runtime_and_history(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        installation = hub.registry.register_distribution(_distribution(tmp_path))
        profile = _profile(hub, installation)
        installation = hub.registry.get_installation(
            installation["installation_id"], include_profiles=True
        )
        instance = installation["instances"][0]
        assert instance["profiles"] == [{
            "profile_id": profile["profile_id"],
            "name": "默认方案",
            "target_id": None,
            "revision": 1,
            "recording_enabled": False,
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
        }]
        # Catalog projections never leak saved field values.
        assert "values" not in instance["profiles"][0]

        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        plan = hub.schedule.create_plan({
            "name": "立即执行固定样例",
            "timezone_id": "UTC",
            "trigger": {"type": "once", "local_datetime": due.replace(tzinfo=None).isoformat(timespec="seconds")},
            "misfire_policy": "catch_up_once",
            "max_lateness_seconds": 60,
            "overlap_policy": "skip",
            "dispatch_mode": "simultaneous",
            "entries": [{
                "host_id": hub.registry.host_id,
                "instance_id": instance["instance_id"],
                "product_id": installation["product_id"],
                "profile_id": profile["profile_id"],
            }],
        })
        hub.run_once(recovery=True)
        deadline = time.monotonic() + 10
        dispatch = None
        while time.monotonic() < deadline:
            rows = hub.schedule.list_dispatches()
            dispatch = rows[0] if rows else None
            if dispatch and dispatch["status"] in {"completed", "failed", "stopped", "rejected"}:
                break
            time.sleep(0.05)
        assert dispatch is not None
        assert dispatch["status"] == "completed"
        assert dispatch["run_id"].startswith("run_")
        occurrence = hub.schedule.list_occurrences(schedule_id=plan["schedule_id"])[0]
        assert occurrence["status"] == "completed"
        assert any(item["event_type"] == "dispatch.accepted" for item in hub.schedule.list_diagnostics())
        assert any(item["event_type"] == "run.completed" for item in hub.schedule.list_diagnostics())
        accepted_again = hub.gateway.accept(LocalDispatchRequest(
            dispatch_id=dispatch["dispatch_id"],
            occurrence_id=dispatch["occurrence_id"],
            schedule_id=dispatch["schedule_id"],
            schedule_revision=dispatch["schedule_revision"],
            entry_id=dispatch["entry_id"],
            host_id=dispatch["host_id"],
            instance_id=dispatch["instance_id"],
            product_id=dispatch["product_id"],
            profile_id=dispatch["profile_id"],
            requested_at=datetime.now(timezone.utc).isoformat(),
        ))
        assert accepted_again.run_id == dispatch["run_id"]
    finally:
        hub.shutdown()


def test_hub_http_has_real_registry_batches_and_honest_remote_state(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    app = FastAPI()
    app.include_router(create_vnext_schedule_hub_router(hub))
    app.include_router(create_vnext_schedule_router(hub.schedule))
    client = TestClient(app)
    try:
        status = client.get("/api/vnext/player-hub")
        assert status.status_code == 200
        remote = status.json()["remote_dispatch"]
        assert remote["available"] is False
        assert remote["state"] == "listener_stopped"
        assert remote["error_id"] == "schedule.remote_dispatch_unavailable"
        assert remote["listener"]["cloud_relay"]["available"] is False
        unknown = client.post(
            "/api/vnext/player-hub/batches",
            json={
                "name": "不可伪造的远端批次",
                "entries": [{
                    "host_id": "remote-host",
                    "instance_id": "remote-instance",
                    "product_id": "remote-product",
                    "profile_id": "remote-profile",
                }],
            },
        )
        assert unknown.status_code in {409, 422}
        assert unknown.json()["detail"]["code"] in {
            "schedule.remote_dispatch_unavailable", "schedule.remote_dispatch_denied",
            "schedule.instance_not_found",
        }
        document = client.get("/openapi.json").json()
        assert document["components"]["schemas"]["InstallationRegisterRequest"]["additionalProperties"] is False
    finally:
        hub.shutdown()


def test_single_task_scheduler_xml_uses_interactive_user_and_one_wake_task() -> None:
    xml = WindowsTaskSchedulerBridge()._xml(
        datetime(2026, 9, 2, 8, 30, tzinfo=timezone.utc)
    )
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
    assert "<WakeToRun>true</WakeToRun>" in xml
    assert xml.count("<TimeTrigger>") == 1
    assert "--player-hub-agent" in xml or "core.vnext.schedule_hub_v6 agent" in xml


def test_registry_rejects_files_changed_after_signed_registration(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        installation = hub.registry.register_distribution(_distribution(tmp_path))
        profile = _profile(hub, installation)
        instance = installation["instances"][0]
        Path(installation["executable_path"]).write_bytes(b"changed after registration")
        try:
            hub.registry.resolve_runtime({
                "host_id": hub.registry.host_id,
                "instance_id": instance["instance_id"],
                "product_id": installation["product_id"],
                "profile_id": profile["profile_id"],
            })
        except ScheduleError as exc:
            assert exc.error_id == "schedule.installation_drift"
        else:  # pragma: no cover - security regression guard
            raise AssertionError("mutated installed runtime was accepted")
    finally:
        hub.shutdown()


def test_dispatch_admission_restart_reuses_run_identity(tmp_path: Path) -> None:
    launched: list[str] = []
    gateway = SQLiteLocalDispatchGateway(
        tmp_path / "admissions.sqlite3",
        launcher=lambda _request, run_id: launched.append(run_id),
    )
    request = LocalDispatchRequest(
        dispatch_id="dispatch-restart", occurrence_id="occurrence-restart",
        schedule_id="schedule-restart", schedule_revision=1,
        entry_id="entry-restart", host_id="host-local",
        instance_id="instance-local", product_id="product-local",
        profile_id="profile-local", requested_at="2026-09-01T00:00:00Z",
    )
    first = gateway.accept(request)
    assert gateway.recover_host_restart() == 1
    second = gateway.accept(LocalDispatchRequest(
        **{**request.as_dict(), "requested_at": "2026-09-01T00:00:10Z"}
    ))
    assert second.run_id == first.run_id
    assert launched == [first.run_id, first.run_id]


def test_hub_reports_database_root_failure_without_partial_start(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    try:
        PlayerHubV6(blocked)
    except ScheduleError as exc:
        assert exc.error_id == "schedule.registry_database_unavailable"
        assert exc.action == "choose_data_directory"
    else:  # pragma: no cover
        raise AssertionError("Hub accepted a file as its database root")


def test_batch_reports_partial_failure_without_blocking_other_instance(tmp_path: Path) -> None:
    hub = PlayerHubV6(tmp_path / "hub")
    try:
        installation = hub.registry.register_distribution(_distribution(tmp_path))
        first_profile = _profile(hub, installation)
        first = installation["instances"][0]
        second = hub.registry.create_instance(
            installation["installation_id"], name="实例 2"
        )
        raw_installation = hub.registry._installation(installation["installation_id"])
        raw_second = hub.registry._instance(second["instance_id"])
        manager = hub.registry._manager(raw_second, raw_installation)
        second_profile = manager.save_profile("", "稍后删除", None, {})["profile"]
        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        plan = hub.schedule.create_plan({
            "name": "部分失败批次",
            "timezone_id": "UTC",
            "trigger": {"type": "once", "local_datetime": due.replace(tzinfo=None).isoformat(timespec="seconds")},
            "misfire_policy": "catch_up_once", "max_lateness_seconds": 60,
            "overlap_policy": "skip", "dispatch_mode": "simultaneous",
            "entries": [
                {"host_id": hub.registry.host_id, "instance_id": first["instance_id"], "product_id": installation["product_id"], "profile_id": first_profile["profile_id"]},
                {"host_id": hub.registry.host_id, "instance_id": second["instance_id"], "product_id": installation["product_id"], "profile_id": second_profile["profile_id"]},
            ],
        })
        manager.delete_profile(second_profile["profile_id"])
        hub.run_once(recovery=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            occurrence = hub.schedule.list_occurrences(schedule_id=plan["schedule_id"])[0]
            if occurrence["status"] in {"partial_failed", "failed"}:
                break
            time.sleep(0.05)
        rows = hub.schedule.list_dispatches(occurrence_id=occurrence["occurrence_id"])
        assert sorted(item["status"] for item in rows) == ["completed", "rejected"]
        assert occurrence["status"] == "partial_failed"
    finally:
        hub.shutdown()
