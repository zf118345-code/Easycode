from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from api.routers.vnext_router import create_vnext_router
from api.routers.workspace_router import create_workspace_router
from core.vnext import vnext_workspace_manager
from core.vnext.recording_storage_v6 import recording_data_root
from core.vnext.replay import VNextReplayService


def _png_bytes(value: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(value.astype(np.uint8), "RGB").save(stream, format="PNG")
    return stream.getvalue()


def _vnext_recording(tmp_path):
    project = tmp_path / "vnext-replay"
    opened = vnext_workspace_manager.open(str(project), initialize=True, project_name="回放测试")
    workspace = opened["workspace"]
    function_id = opened["programs"][0]["function_id"]
    pattern = np.random.default_rng(20260829).integers(0, 256, size=(14, 18, 3), dtype=np.uint8)
    asset = vnext_workspace_manager.import_asset(
        workspace["workspace_id"], workspace["generation"],
        category="page", folder="", file_name="sale.png", display_name="开售按钮",
        content_base64=base64.b64encode(_png_bytes(pattern)).decode("ascii"), source="test",
    )["asset"]
    loaded = vnext_workspace_manager.load_program(
        workspace["workspace_id"], workspace["generation"], function_id,
    )
    inserted = vnext_workspace_manager.apply_program_command(
        workspace["workspace_id"], workspace["generation"], function_id,
        loaded["revision"],
        {
            "kind": "insert_call",
            "function_id": "official.image.find",
            "arguments": {
                "official.image.find.parameter.image": {
                    "value_id": "value_replay_image", "kind": "asset_ref",
                    "asset_id": asset["asset_id"], "asset_kind": "image",
                },
                "official.image.find.parameter.similarity": {
                    "value_id": "value_replay_similarity", "kind": "float64", "value": 0.95,
                },
                "official.image.find.parameter.region": {
                    "value_id": "value_replay_region", "kind": "rect",
                    "x": 45, "y": 30, "width": 18, "height": 14,
                },
                "official.image.find.parameter.frame": {
                    "value_id": "value_replay_frame", "kind": "null",
                },
            },
            "location": {"block": "root"},
        },
    )
    assert inserted["diagnostics"] == []

    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    frame[30:44, 45:63] = pattern
    content = _png_bytes(frame)
    session_id = "frame_recording_vnext_test"
    session = project / "recordings" / session_id
    session.mkdir(parents=True)
    frame_path = session / "frame_00000001.png"
    frame_path.write_bytes(content)
    record = {
        "index": 1, "file": frame_path.name, "captured_at": "2026-08-29T10:00:00+08:00",
        "width": 120, "height": 80, "bytes": len(content), "change_score": 1.0,
        "screen_region": [100, 200, 220, 280],
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    (session / "frames.jsonl").write_text(
        json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    (session / "session.json").write_text(json.dumps({
        "schema_version": 2, "session_id": session_id, "status": "stopped",
        "started_at": "2026-08-29T10:00:00+08:00", "frame_count": 1,
        "target_id": "target_replay_windows", "target_kind": "windows",
        "target_title": "回放测试窗口",
    }, ensure_ascii=False), encoding="utf-8")
    return workspace, session_id, function_id


def test_vnext_replay_compiles_program_document_and_explains_image_match(tmp_path):
    workspace, session_id, function_id = _vnext_recording(tmp_path)

    result = vnext_workspace_manager.analyze_replay_frame(
        workspace["workspace_id"], workspace["generation"], session_id, 1,
    )

    assert result["entry_function_id"] == function_id
    assert result["ecir_revision"].startswith("sha256:")
    assert result["matched_count"] == 1
    analysis = result["analyses"][0]
    assert analysis["function_id"] == "official.image.find"
    assert analysis["matched"] is True
    assert analysis["score"] >= 0.95
    assert analysis["center"] == [54, 37]


def test_vnext_replay_api_lists_frames_and_runs_program_analysis(tmp_path):
    workspace, session_id, _function_id = _vnext_recording(tmp_path)
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    headers = {
        "X-Workspace-Id": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }

    sessions = client.get("/api/vnext/replay/sessions", headers=headers)
    frames = client.get(f"/api/vnext/replay/sessions/{session_id}/frames", headers=headers)
    image = client.get(
        f"/api/vnext/replay/sessions/{session_id}/frames/1/image?thumbnail=true",
        headers=headers,
    )
    report = client.post("/api/vnext/replay/analyze-session", headers=headers, json={
        "session_id": session_id, "changes_only": False, "step": 1, "max_frames": 100,
    })

    assert sessions.status_code == 200 and sessions.json()["sessions"][0]["frame_count"] == 1
    assert frames.status_code == 200 and frames.json()["frames"][0]["index"] == 1
    assert image.status_code == 200 and image.headers["content-type"].startswith("image/jpeg")
    assert report.status_code == 200, report.text
    assert report.json()["coverage"][0]["matched_frames"] == 1
    assert report.json()["error_frame_count"] == 0


def test_replay_analysis_catalog_reports_incomplete_program_without_workspace_conflict(tmp_path):
    opened = vnext_workspace_manager.open(
        str(tmp_path / "replay-incomplete"), initialize=True, project_name="未完成回放项目",
    )
    workspace = opened["workspace"]
    function_id = opened["programs"][0]["function_id"]
    loaded = vnext_workspace_manager.load_program(
        workspace["workspace_id"], workspace["generation"], function_id,
    )
    vnext_workspace_manager.apply_program_command(
        workspace["workspace_id"], workspace["generation"], function_id, loaded["revision"],
        {
            "kind": "insert_call",
            "function_id": "official.image.find",
            "arguments": {},
            "location": {"block": "root"},
        },
    )
    app = FastAPI()
    app.include_router(create_vnext_router())
    response = TestClient(app).get("/api/vnext/replay/analysis-catalog", headers={
        "X-Workspace-Id": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["analyses"] == []
    assert "必填" in payload["unavailable_reason"]
    assert payload["diagnostics"]


def test_replay_analysis_catalog_treats_a_valid_program_without_analysis_as_an_empty_state(tmp_path):
    opened = vnext_workspace_manager.open(
        str(tmp_path / "replay-without-analysis"), initialize=True, project_name="无回放分析项目",
    )
    workspace = opened["workspace"]
    app = FastAPI()
    app.include_router(create_vnext_router())
    response = TestClient(app).get("/api/vnext/replay/analysis-catalog", headers={
        "X-Workspace-Id": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    })

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "unavailable_reason": "当前入口没有可回放的图像或 OCR 语句。",
        "diagnostics": [],
        "analyses": [],
    }


def test_vnext_recording_api_is_workspace_scoped_and_strict(monkeypatch, tmp_path):
    opened = vnext_workspace_manager.open(str(tmp_path / "recording-api"), initialize=True)
    workspace = opened["workspace"]
    headers = {
        "X-Workspace-Id": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }
    calls = []
    monkeypatch.setattr(vnext_workspace_manager, "recording_status", lambda *_args: {"active": False, "status": "idle"})
    monkeypatch.setattr(
        vnext_workspace_manager,
        "start_recording",
        lambda workspace_id, generation, target_id, options: calls.append(
            (workspace_id, generation, target_id, options)
        ) or {"active": True, "status": "recording"},
    )
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)

    status = client.get("/api/vnext/recording/status", headers=headers)
    started = client.post("/api/vnext/recording/start", headers=headers, json={
        "target_id": "target_windows", "target_fps": 20,
        "recording_mode": "changed_frames", "change_threshold": 0.01,
    })
    invalid = client.post("/api/vnext/recording/start", headers=headers, json={
        "target_id": "target_windows", "unknown_option": True,
    })

    assert status.status_code == 200 and status.json()["active"] is False
    assert started.status_code == 200 and started.json()["active"] is True
    assert calls[0][2] == "target_windows"
    assert calls[0][3]["target_fps"] == 20
    assert invalid.status_code == 422


def test_vnext_timeline_keeps_committed_frames_before_partial_crash_line(tmp_path):
    workspace, session_id, _function_id = _vnext_recording(tmp_path)
    frames_path = (
        tmp_path / "vnext-replay" / "recordings" / session_id / "frames.jsonl"
    )
    with frames_path.open("a", encoding="utf-8") as stream:
        stream.write('{"index": 2, "file":')

    timeline = vnext_workspace_manager.replay_frames(
        workspace["workspace_id"], workspace["generation"], session_id, 0, 200,
    )
    image, path = vnext_workspace_manager.replay_frame_bytes(
        workspace["workspace_id"], workspace["generation"], session_id, 1,
        thumbnail=False,
    )

    assert timeline["total"] == 1
    assert timeline["frames"][0]["screen_region"] == [100, 200, 220, 280]
    assert image.startswith(b"\x89PNG")
    assert path.endswith("frame_00000001.png")


def test_vnext_recorded_frame_is_a_frozen_capture_source(monkeypatch, tmp_path):
    from core.services.capture_session_service import CaptureSessionService

    workspace, recording_session_id, _function_id = _vnext_recording(tmp_path)
    capture_session_id = "vnext_replay_capture"
    with CaptureSessionService._lock:
        CaptureSessionService._ui_sessions.clear()
        CaptureSessionService._snapshots.clear()
        CaptureSessionService._active_snapshot_id = None
    CaptureSessionService.register_ui_session({
        **workspace,
        "session_id": capture_session_id,
        "workspace_kind": "vnext",
        "workspace_generation": workspace["generation"],
        "execution_state": "idle",
    })

    snapshot = CaptureSessionService.create_recording_snapshot(
        workspace["project_path"], recording_session_id, 1,
        session_id=capture_session_id, include_image=False,
    )
    stored = CaptureSessionService.get_snapshot(snapshot["snapshot_id"], include_image=False)

    assert snapshot["backend"] == "recording_replay"
    assert snapshot["region"] == [100, 200, 220, 280]
    assert stored["source"]["kind"] == "recording"
    assert stored["source"]["frame_index"] == 1
    CaptureSessionService.close_capture(snapshot["snapshot_id"])


def test_legacy_topology_replay_routes_are_inert_410_boundaries():
    app = FastAPI()
    app.include_router(create_workspace_router(None, None))
    client = TestClient(app)

    for path in (
        "/api/frame-recording/analyze",
        "/api/frame-recording/analyze-session",
    ):
        response = client.post(path, json={"legacy": "topology-payload"})
        assert response.status_code == 410
        assert response.json()["detail"]["code"] == "topology_replay_retired"


def test_replay_analysis_input_is_content_addressed_immutable_and_reports_append(tmp_path):
    workspace, session_id, _function_id = _vnext_recording(tmp_path)
    project = tmp_path / "vnext-replay"
    program_before = {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((project / "program").rglob("*")) if path.is_file()
    }

    first = vnext_workspace_manager.analyze_replay_frame(
        workspace["workspace_id"], workspace["generation"], session_id, 1,
    )
    second = vnext_workspace_manager.analyze_replay_frame(
        workspace["workspace_id"], workspace["generation"], session_id, 1,
    )

    assert first["analysis_input_bundle_id"] == second["analysis_input_bundle_id"]
    assert first["analysis_run_id"] != second["analysis_run_id"]
    reports = vnext_workspace_manager.replay_analysis_reports(
        workspace["workspace_id"], workspace["generation"], session_id,
    )
    latest = next(item for item in reports if item["analysis_run_id"] == second["analysis_run_id"])
    assert latest["previous_analysis_run_id"] == first["analysis_run_id"]
    bundle = recording_data_root(str(project)) / "analysis-inputs" / first["analysis_input_bundle_id"]
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["immutable"] is True
    assert {item["category"] for item in manifest["components"]} >= {
        "frames", "program", "ecir", "resources", "parameters", "implementation",
    }
    assert any(
        item["category"] == "resources" and item["logical_name"] != "assets/registry.json"
        for item in manifest["components"]
    )
    program_after = {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((project / "program").rglob("*")) if path.is_file()
    }
    assert program_after == program_before


def test_replay_server_rejects_side_effect_or_extension_analysis_id():
    ecir = {
        "functions": [{
            "function_id": "project.main",
            "instructions": [{
                "instruction_id": "statement_input",
                "opcode": "input.click",
                "function_id": "official.input.click",
                "arguments": {},
            }, {
                "instruction_id": "statement_extension",
                "opcode": "extension.call",
                "function_id": "extension.vendor.find",
                "arguments": {},
            }],
        }],
    }

    with pytest.raises(HTTPException) as rejected:
        VNextReplayService._replayable_calls(
            ecir, ["project.main:statement_input"],
        )
    assert rejected.value.status_code == 422
    assert "官方无副作用回放目录" in str(rejected.value.detail) or "没有可回放" in str(rejected.value.detail)


def test_default_and_reproducible_exports_disclose_different_privacy_closures(tmp_path):
    workspace, session_id, _function_id = _vnext_recording(tmp_path)
    analyzed = vnext_workspace_manager.analyze_replay_frame(
        workspace["workspace_id"], workspace["generation"], session_id, 1,
    )
    default = vnext_workspace_manager.create_replay_export(
        workspace["workspace_id"], workspace["generation"], session_id,
        mode="default", analysis_run_ids=[analyzed["analysis_run_id"]],
        include_categories=[], frame_indices=[1],
    )
    reproducible = vnext_workspace_manager.create_replay_export(
        workspace["workspace_id"], workspace["generation"], session_id,
        mode="reproducible", analysis_run_ids=[analyzed["analysis_run_id"]],
        include_categories=[
            "program", "ecir", "resources", "parameters", "implementation",
        ], frame_indices=[1],
    )

    with zipfile.ZipFile(default["path"]) as archive:
        names = set(archive.namelist())
        privacy = json.loads(archive.read("privacy-manifest.json"))
        assert not any(name.startswith("analysis-inputs/") for name in names)
        assert privacy["contains_project_program"] is False
        assert privacy["automatic_upload"] is False
        assert privacy["exported_frame_indices"] == [1]
    with zipfile.ZipFile(reproducible["path"]) as archive:
        names = set(archive.namelist())
        privacy = json.loads(archive.read("privacy-manifest.json"))
        assert any(name.startswith("analysis-inputs/") for name in names)
        assert privacy["contains_project_program"] is True
        assert privacy["contains_resources"] is True
        assert "content-manifest.json" in names
