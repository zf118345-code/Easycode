from __future__ import annotations

import json
import threading
import time
from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from api.routers.vnext_router import create_vnext_router
from core.vnext.player_bundle import PlayerBundleError, VNextPlayerBundleManager, vnext_player_bundle_manager
from core.vnext.recorder_v6 import V6FrameRecorder, V6RecordingError
from core.vnext.recording_storage_v6 import (
    DROP_INDEX,
    FRAME_INDEX,
    RECORDING_MANIFEST,
    SEGMENT_INDEX,
    TERMINAL_RECORD,
    RecordingStorageV6,
)
from core.vnext.replay import VNextReplayService


def _project(tmp_path: Path, project_id: str = "project_recording_v6") -> Path:
    project = tmp_path / project_id
    project.mkdir()
    (project / "project.json").write_text(json.dumps({
        "project_id": project_id,
        "name": "录制回放契约测试",
    }, ensure_ascii=False), encoding="utf-8")
    return project


def _wait(recorder: V6FrameRecorder, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    while recorder.get_state()["active"] and time.monotonic() < deadline:
        time.sleep(0.01)
    state = recorder.get_state()
    assert state["active"] is False, state
    return state


def _record_sequence(
    tmp_path: Path,
    monkeypatch,
    *,
    strategy: str,
    frames: list[Image.Image],
    recorder: V6FrameRecorder | None = None,
    target_snapshot=None,
) -> tuple[Path, V6FrameRecorder, dict, list[str]]:
    monkeypatch.setenv("EASYCODE_RECORDING_DATA_ROOT", str(tmp_path / "recording-data"))
    project = _project(tmp_path, f"project_{strategy}_{len(frames)}")
    recorder = recorder or V6FrameRecorder()
    released: list[str] = []
    lock = threading.Lock()
    cursor = 0

    def capture() -> Image.Image:
        nonlocal cursor
        with lock:
            index = min(cursor, len(frames) - 1)
            cursor += 1
            should_stop = cursor >= len(frames)
        if should_stop:
            recorder.request_stop("completed")
        return frames[index].copy()

    def snapshot() -> dict:
        if target_snapshot is not None:
            return target_snapshot(cursor)
        return {
            "target_id": "target_windows",
            "target_kind": "windows",
            "target_title": "测试窗口",
            "dpi": 96,
        }

    started = recorder.start(
        str(project),
        {
            "strategy": strategy,
            "target_fps": 120,
            "queue_capacity": 4,
            "min_free_bytes": 64 * 1024 * 1024,
            "max_duration_ms": 30_000,
            "diagnostic_pre_frames": 4,
            "diagnostic_post_frames": 2,
        },
        capture_provider=capture,
        capture_release=lambda: released.append("released"),
        target_snapshot_provider=snapshot,
        capture_backend="test:deterministic-frame-source",
    )
    return project, recorder, {**started, **_wait(recorder)}, released


def test_all_frames_contract_is_lossless_segmented_and_releases_once(tmp_path, monkeypatch):
    frames = [
        Image.new("RGB", (40, 24), (index * 20, 30, 60))
        for index in range(1, 5)
    ]
    frames[-1] = Image.new("RGB", (24, 40), (120, 30, 60))
    project, _recorder, state, released = _record_sequence(
        tmp_path,
        monkeypatch,
        strategy="all_frames",
        frames=frames,
        target_snapshot=lambda cursor: {
            "target_id": "target_windows",
            "target_kind": "windows",
            "target_title": "测试窗口",
            "orientation": "portrait" if cursor >= 4 else "landscape",
            "dpi": 120 if cursor >= 4 else 96,
        },
    )

    assert state["terminal_reason"] == "completed"
    assert state["frame_count"] == 4
    assert state["segment_count"] == 2
    assert released == ["released"]
    verification = RecordingStorageV6.verify_session(str(project), state["session_id"])
    assert verification["ok"] is True, verification
    detail = RecordingStorageV6.session_detail(str(project), state["session_id"])
    opened = [item for item in detail["segments"] if item["event"] == "opened"]
    assert [(item["width"], item["height"]) for item in opened] == [(40, 24), (24, 40)]


def test_changed_and_diagnostic_strategies_preserve_truthful_gaps_and_markers(tmp_path, monkeypatch):
    unchanged = Image.new("RGB", (48, 32), "navy")
    changed = Image.new("RGB", (48, 32), "orange")
    project, _recorder, changed_state, _released = _record_sequence(
        tmp_path,
        monkeypatch,
        strategy="changed_frames",
        frames=[unchanged, unchanged, unchanged, changed],
    )
    assert changed_state["frame_count"] == 2
    assert changed_state["policy_skipped_frame_count"] == 2
    detail = RecordingStorageV6.session_detail(str(project), changed_state["session_id"])
    assert detail["drops"][0]["kind"] == "policy_filtered"
    assert detail["drops"][0]["count"] == 2

    gate = threading.Event()
    diagnostic = V6FrameRecorder()
    calls = 0
    diagnostic_project = _project(tmp_path, "project_diagnostic_marker")
    monkeypatch.setenv("EASYCODE_RECORDING_DATA_ROOT", str(tmp_path / "recording-data"))

    def capture() -> Image.Image:
        nonlocal calls
        calls += 1
        if calls == 2:
            assert gate.wait(2)
        if calls >= 5:
            diagnostic.request_stop("completed")
        return Image.new("RGB", (32, 20), (calls * 20 % 255, 10, 80))

    diagnostic.start(
        str(diagnostic_project),
        {
            "strategy": "diagnostic", "target_fps": 120, "queue_capacity": 4,
            "diagnostic_pre_frames": 3, "diagnostic_post_frames": 2,
            "min_free_bytes": 64 * 1024 * 1024,
        },
        capture_provider=capture,
        capture_release=lambda: None,
        target_snapshot_provider=lambda: {
            "target_id": "adb-device", "target_kind": "android_adb", "target_title": "模拟器",
        },
        capture_backend="test:adb-frame-source",
    )
    marker = diagnostic.mark_event("故障前证据")
    gate.set()
    diagnostic_state = _wait(diagnostic)
    assert marker["label"] == "故障前证据"
    assert diagnostic_state["marker_count"] == 1
    assert diagnostic_state["frame_count"] >= 3
    diagnostic_detail = RecordingStorageV6.session_detail(
        str(diagnostic_project), diagnostic_state["session_id"],
    )
    assert diagnostic_detail["markers"][0]["label"] == "故障前证据"


def test_bounded_writer_reports_backpressure_instead_of_fake_continuity(tmp_path, monkeypatch):
    recorder = V6FrameRecorder()
    original_write = recorder._write_packet

    def slow_write(packet):
        if int(packet["capture_sequence"]) > 1:
            time.sleep(0.04)
        return original_write(packet)

    monkeypatch.setattr(recorder, "_write_packet", slow_write)
    frames = [
        Image.fromarray(np.full((32, 48, 3), index % 255, dtype=np.uint8), "RGB")
        for index in range(36)
    ]
    project, _recorder, state, _released = _record_sequence(
        tmp_path, monkeypatch, strategy="all_frames", frames=frames, recorder=recorder,
    )
    assert state["dropped_frame_count"] > 0
    assert state["frame_count"] + state["dropped_frame_count"] == state["capture_count"]
    detail = RecordingStorageV6.session_detail(str(project), state["session_id"])
    assert any(item["kind"] == "backpressure" for item in detail["drops"])
    saved_capture_sequences = {
        int(item["capture_sequence"])
        for item in RecordingStorageV6.list_frames(str(project), state["session_id"], 0, 500)["frames"]
    }
    missing = set(range(1, state["capture_count"] + 1)) - saved_capture_sequences
    covered = {
        sequence
        for item in detail["drops"] if item["kind"] == "backpressure"
        for sequence in range(item["start_capture_sequence"], item["end_capture_sequence"] + 1)
    }
    assert missing == covered


def test_disk_start_guard_and_process_interruption_recovery_are_truthful(tmp_path, monkeypatch):
    import core.vnext.recorder_v6 as recorder_module

    monkeypatch.setenv("EASYCODE_RECORDING_DATA_ROOT", str(tmp_path / "recording-data"))
    project = _project(tmp_path, "project_disk_guard")
    recorder = V6FrameRecorder()
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(recorder_module.shutil, "disk_usage", lambda _path: usage(100, 99, 1))
    with pytest.raises(V6RecordingError, match="磁盘可用空间"):
        recorder.start(
            str(project), {"min_free_bytes": 64 * 1024 * 1024},
            capture_provider=lambda: Image.new("RGB", (10, 10)),
            capture_release=lambda: None,
            target_snapshot_provider=lambda: {"target_id": "target", "target_kind": "windows"},
            capture_backend="test",
        )
    root = RecordingStorageV6.recordings_root(str(project))
    assert not [item for item in root.iterdir() if item.is_dir()]

    monkeypatch.undo()
    project, _recorder, state, _released = _record_sequence(
        tmp_path,
        monkeypatch,
        strategy="all_frames",
        frames=[Image.new("RGB", (20, 12), "red"), Image.new("RGB", (20, 12), "blue")],
    )
    session_dir = RecordingStorageV6.session_dir(str(project), state["session_id"])
    manifest = json.loads((session_dir / RECORDING_MANIFEST).read_text(encoding="utf-8"))
    manifest.update({"final": False, "status": "recording", "process_id": 2_147_483_647})
    (session_dir / RECORDING_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8",
    )
    (session_dir / TERMINAL_RECORD).unlink()

    recovered = RecordingStorageV6.list_sessions(str(project))[0]
    assert recovered["recovered"] is True
    assert recovered["terminal_reason"] == "process_interrupted"
    assert recovered["frame_count"] == 2
    assert RecordingStorageV6.verify_session(str(project), state["session_id"])["ok"] is True


def test_corrupt_v3_pixels_block_analysis_before_any_adapter_runs(tmp_path, monkeypatch):
    project, _recorder, state, _released = _record_sequence(
        tmp_path,
        monkeypatch,
        strategy="all_frames",
        frames=[Image.new("RGB", (20, 12), "red"), Image.new("RGB", (20, 12), "blue")],
    )
    frame = RecordingStorageV6.resolve_frame(str(project), state["session_id"], 1)
    frame.path.write_bytes(b"tampered")

    with pytest.raises(Exception) as rejected:
        VNextReplayService.analyze_frame(
            str(project), {"functions": []}, state["session_id"], 1,
        )
    assert "完整性校验失败" in str(rejected.value)


def _manager_for_profiles(tmp_path: Path, monkeypatch, target_type: str = "windows") -> VNextPlayerBundleManager:
    monkeypatch.setenv("EASYCODE_PLAYER_DATA_DIR", str(tmp_path / "player-data"))
    runtime = tmp_path / f"runtime-{target_type}"
    runtime.mkdir()
    manager = VNextPlayerBundleManager()
    manager._runtime_root = str(runtime)
    manager._manifest = {"project_id": f"player-recording-{target_type}"}
    manager._project = {
        "targets": [{
            "target_id": "target_1", "name": "目标", "type": target_type,
            **({
                "window_title": "Game", "window_match": "contains",
                "work_area": {"mode": "client"}, "allow_physical_fallback": True,
            } if target_type == "windows" else {}),
        }],
        "default_target_id": "target_1",
    }
    manager._ecir = {
        "ecir_version": 1, "entry_function_id": "function_main",
        "supported_platforms": ["windows"], "targets": manager._project["targets"],
        "project_variables": [], "functions": [{
            "function_id": "function_main", "parameter_definitions": [], "instructions": [],
        }],
    }
    manager._form = {
        "schema_version": 3,
        "title": "Player",
        "features": {"recording": True},
        "pages": [],
    }
    manager._base_form = manager._form.copy()
    return manager


def test_unpublished_recording_feature_rejects_profile_enable_and_has_no_history(tmp_path, monkeypatch):
    manager = _manager_for_profiles(tmp_path, monkeypatch)
    manager._form["features"]["recording"] = False

    with pytest.raises(Exception, match="未发布运行录制能力"):
        manager.save_profile("", "普通方案", "target_1", {}, recording={
            "enabled": True,
            "confirm_current_revision": True,
        })

    profile = manager.save_profile("", "普通方案", "target_1", {})["profile"]
    plan = manager._player_recording_plan({
        "profile_id": profile["profile_id"],
        "profile_revision": profile["revision"],
    })
    assert plan == {
        "enabled": False,
        "status": "disabled",
        "reason": "feature_not_published",
    }
    assert manager.recording_sessions() == {"sessions": []}


def test_player_recording_consent_is_bound_to_exact_profile_revision_and_target(tmp_path, monkeypatch):
    manager = _manager_for_profiles(tmp_path, monkeypatch)
    settings = {
        "enabled": True,
        "confirm_current_revision": True,
        "strategy": "changed_frames",
        "target_fps": 15,
        "max_duration_ms": 60_000,
        "max_session_bytes": 32 * 1024 * 1024,
        "min_free_bytes": 64 * 1024 * 1024,
    }
    first = manager.save_profile("", "录制方案", "target_1", {}, recording=settings)["profile"]
    assert first["revision"] == 1
    assert first["recording"]["confirmed_profile_revision"] == 1
    assert manager._player_recording_plan({
        "profile_id": first["profile_id"], "profile_revision": 1,
    })["enabled"] is True

    second = manager.save_profile(
        first["profile_id"], "录制方案改名", "target_1", {}, expected_revision=1,
    )["profile"]
    stale = manager._player_recording_plan({
        "profile_id": first["profile_id"], "profile_revision": 2,
    })
    assert stale["enabled"] is False
    assert stale["reason"] == "profile_revision_not_confirmed"

    third = manager.save_profile(
        first["profile_id"], "录制方案改名", "target_1", {},
        expected_revision=2, recording=settings,
    )["profile"]
    override = manager._player_recording_plan({
        "profile_id": first["profile_id"], "profile_revision": third["revision"],
        "target_id": "another-target",
    })
    assert override["enabled"] is False
    assert override["reason"] == "target_override_not_confirmed"


def test_android_local_player_recording_uses_the_shared_profile_contract(tmp_path, monkeypatch):
    manager = _manager_for_profiles(tmp_path, monkeypatch, "android_local")
    profile = manager.save_profile("", "手机方案", "target_1", {}, recording={
        "enabled": True,
        "confirm_current_revision": True,
    })["profile"]
    assert profile["recording"]["enabled"] is True
    assert profile["recording"]["confirmed_profile_revision"] == profile["revision"]
    assert manager._player_recording_plan({
        "profile_id": profile["profile_id"],
        "profile_revision": profile["revision"],
    })["enabled"] is True


def test_player_recording_http_status_and_stop_are_real_manager_endpoints(monkeypatch):
    monkeypatch.setattr(vnext_player_bundle_manager, "available", lambda: True)
    monkeypatch.setattr(vnext_player_bundle_manager, "recording_status", lambda: {
        "active": True, "status": "recording", "frame_count": 12,
    })
    monkeypatch.setattr(vnext_player_bundle_manager, "stop_recording", lambda: {
        "active": False, "status": "stopped", "terminal_reason": "user_stopped",
    })
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)

    assert client.get("/api/vnext/player/runtime/recording").json()["frame_count"] == 12
    stopped = client.post("/api/vnext/player/runtime/recording/stop")
    assert stopped.status_code == 200
    assert stopped.json()["terminal_reason"] == "user_stopped"


def test_player_recording_failure_does_not_replace_or_cancel_runtime_task(tmp_path, monkeypatch):
    manager = _manager_for_profiles(tmp_path, monkeypatch)
    target = manager._project["targets"][0]
    ecir = manager._ecir
    monkeypatch.setattr(manager, "_prepare_execution", lambda _payload: (target, ecir, "target_1"))
    monkeypatch.setattr(manager, "_dangerous_operation_requirements", lambda _ecir: [])
    monkeypatch.setattr(manager, "_validated_dangerous_confirmations", lambda *_args: [])
    monkeypatch.setattr(manager, "_player_recording_plan", lambda _payload: {
        "enabled": True, "strategy": "changed_frames", "target_fps": 15,
        "max_duration_ms": 60_000, "max_session_bytes": 32 * 1024 * 1024,
        "min_free_bytes": 64 * 1024 * 1024,
    })
    monkeypatch.setattr(
        "core.vnext.player_bundle.vnext_runtime.start",
        lambda *_args, **_kwargs: {"execution_id": "run-still-alive", "status": "queued"},
    )
    monkeypatch.setattr(manager._recording, "start", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("disk offline")))

    result = manager.start({})

    assert result["execution_id"] == "run-still-alive"
    assert result["status"] == "queued"
    assert result["recording"]["status"] == "error"
    assert result["recording"]["terminal_reason"] == "driver_failed"
    assert "disk offline" in result["recording"]["last_error"]
