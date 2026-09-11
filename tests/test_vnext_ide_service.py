from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.workspace import VNextWorkspaceError, VNextWorkspaceManager


def _workspace(manager: VNextWorkspaceManager, path: Path) -> tuple[dict, str]:
    opened = manager.open(str(path), initialize=True, project_name=path.name)
    assert opened["workspace"] is not None
    return opened["workspace"], opened["programs"][0]["function_id"]


def _headers(workspace: dict) -> dict[str, str]:
    return {
        "X-Workspace-ID": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }


def _insert_log(manager: VNextWorkspaceManager, workspace: dict, function_id: str, text: str) -> dict:
    loaded = manager.load_program(workspace["workspace_id"], workspace["generation"], function_id)
    return manager.apply_program_command(
        workspace["workspace_id"], workspace["generation"], function_id,
        loaded["revision"],
        {
            "kind": "insert_call",
            "function_id": "official.log.output",
            "arguments": {
                "official.log.output.parameter.content": {
                    "value_id": f"value_{len(text)}_{function_id[-6:]}",
                    "kind": "string", "value": text,
                },
            },
            "location": {"block": "root"},
        },
    )


def test_breakpoints_use_function_and_statement_ids_across_reopen(tmp_path: Path):
    project = tmp_path / "debug-roundtrip"
    manager = VNextWorkspaceManager()
    workspace, function_id = _workspace(manager, project)
    inserted = _insert_log(manager, workspace, function_id, "断点测试")
    statement_id = inserted["selected_statement_id"]

    saved = manager.save_debug_settings(
        workspace["workspace_id"], workspace["generation"],
        {function_id: [statement_id, statement_id]},
    )

    assert saved == {
        "schema_version": 2,
        "breakpoints": {function_id: [statement_id]},
    }
    reopened_manager = VNextWorkspaceManager()
    reopened = reopened_manager.open(str(project))["workspace"]
    assert reopened_manager.debug_settings(
        reopened["workspace_id"], reopened["generation"],
    ) == saved


def test_debug_settings_reject_unknown_program_identity(tmp_path: Path):
    manager = VNextWorkspaceManager()
    workspace, function_id = _workspace(manager, tmp_path / "debug-identity-guard")

    with pytest.raises(VNextWorkspaceError, match="项目函数不存在"):
        manager.save_debug_settings(
            workspace["workspace_id"], workspace["generation"],
            {"src/main.easy": ["statement_a"]},
        )
    with pytest.raises(VNextWorkspaceError, match="不包含语句"):
        manager.save_debug_settings(
            workspace["workspace_id"], workspace["generation"],
            {function_id: ["statement_missing"]},
        )


def test_workspace_search_reads_program_documents_and_is_identity_guarded(tmp_path: Path):
    manager = VNextWorkspaceManager()
    first, function_id = _workspace(manager, tmp_path / "search-first")
    _insert_log(manager, first, function_id, "Needle")

    result = manager.search_workspace(
        first["workspace_id"], first["generation"], "NEEDLE", limit=1,
    )
    assert result["truncated"] is False
    assert result["results"][0]["kind"] == "program"
    assert result["results"][0]["function_id"] == function_id
    assert result["results"][0]["statement_id"]

    second, _ = _workspace(manager, tmp_path / "search-second")
    with pytest.raises(VNextWorkspaceError, match="工作区"):
        manager.search_workspace(first["workspace_id"], first["generation"], "needle")
    assert manager.search_workspace(
        second["workspace_id"], second["generation"], "",
    ) == {"query": "", "results": [], "truncated": False}


def test_debug_and_program_search_api_contracts(tmp_path: Path):
    manager = VNextWorkspaceManager()
    _workspace(manager, tmp_path / "ide-api")
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    opened = client.post("/api/vnext/workspaces/open", json={
        "path": str(tmp_path / "ide-api"), "initialize": False, "project_name": "ide-api",
    })
    assert opened.status_code == 200, opened.text
    api_workspace = opened.json()["workspace"]
    function_id = opened.json()["programs"][0]["function_id"]
    headers = _headers(api_workspace)

    loaded = client.get(f"/api/vnext/programs/{function_id}", headers=headers).json()
    inserted = client.post(
        f"/api/vnext/programs/{function_id}/commands",
        headers=headers,
        json={
            "expected_revision": loaded["revision"],
            "command": {
                "kind": "insert_call", "function_id": "official.log.output",
                "arguments": {
                    "official.log.output.parameter.content": {
                        "value_id": "value_api_search", "kind": "string", "value": "API搜索词",
                    },
                },
                "location": {"block": "root"},
            },
        },
    )
    assert inserted.status_code == 200, inserted.text
    statement_id = inserted.json()["selected_statement_id"]
    saved = client.put("/api/vnext/debug-settings", headers=headers, json={
        "breakpoints": {function_id: [statement_id]},
    })
    assert saved.status_code == 200, saved.text
    assert client.get("/api/vnext/debug-settings", headers=headers).json() == saved.json()

    searched = client.get("/api/vnext/search", headers=headers, params={"query": "API搜索词"})
    assert searched.status_code == 200, searched.text
    assert searched.json()["results"][0]["function_id"] == function_id


def test_program_rename_keeps_breakpoints_and_delete_prunes_them(tmp_path: Path):
    manager = VNextWorkspaceManager()
    project = tmp_path / "debug-function-lifecycle"
    workspace, _entry_function_id = _workspace(manager, project)
    created = manager.create_program(workspace["workspace_id"], workspace["generation"], "旧函数")
    function_id = created["document"]["function"]["function_id"]
    inserted = _insert_log(manager, workspace, function_id, "子函数")
    statement_id = inserted["selected_statement_id"]
    manager.save_debug_settings(
        workspace["workspace_id"], workspace["generation"],
        {function_id: [statement_id]},
    )

    renamed = manager.rename_program(
        workspace["workspace_id"], workspace["generation"], function_id,
        expected_revision=inserted["revision"], display_name="新函数",
    )
    assert renamed["document"]["function"]["function_id"] == function_id
    assert manager.debug_settings(
        workspace["workspace_id"], workspace["generation"],
    )["breakpoints"] == {function_id: [statement_id]}

    manager.delete_program(
        workspace["workspace_id"], workspace["generation"], function_id,
        expected_revision=renamed["revision"],
    )
    assert manager.debug_settings(
        workspace["workspace_id"], workspace["generation"],
    )["breakpoints"] == {}


def test_view_state_is_separate_sanitized_and_corruption_falls_back_to_defaults(tmp_path: Path):
    manager = VNextWorkspaceManager()
    project = tmp_path / 'view-state'
    workspace, function_id = _workspace(manager, project)
    inserted = _insert_log(manager, workspace, function_id, '折叠位置')
    statement_id = inserted['selected_statement_id']
    saved = manager.save_view_state(workspace['workspace_id'], workspace['generation'], {
        'active_view': 'variables',
        'active_function_id': function_id,
        'collapsed_statement_ids': {function_id: [statement_id, 'statement_missing']},
        'scroll_offsets': {'program': 123},
        'panel_sizes': {'library': 280},
    })
    assert saved['active_view'] == 'variables'
    assert saved['collapsed_statement_ids'] == {function_id: [statement_id]}

    (project / '.easycode' / 'view-state.json').write_text('{broken', encoding='utf-8')
    defaulted = manager.view_state(workspace['workspace_id'], workspace['generation'])
    assert defaulted['active_view'] == 'program'
    assert defaulted['active_function_id'] == ''
    assert defaulted['collapsed_statement_ids'] == {}


def test_view_state_http_roundtrip(tmp_path: Path):
    app = FastAPI(); app.include_router(create_vnext_router()); client = TestClient(app)
    opened = client.post('/api/vnext/workspaces/open', json={
        'path': str(tmp_path / 'view-state-http'), 'initialize': True, 'project_name': '视图状态',
    }).json()
    headers = _headers(opened['workspace'])
    function_id = opened['programs'][0]['function_id']
    saved = client.put('/api/vnext/view-state', headers=headers, json={
        'active_view': 'player', 'active_function_id': function_id,
        'collapsed_statement_ids': {}, 'scroll_offsets': {}, 'panel_sizes': {},
    })
    assert saved.status_code == 200, saved.text
    assert client.get('/api/vnext/view-state', headers=headers).json()['active_view'] == 'player'
