from __future__ import annotations

from pathlib import Path


def open_workspace(client, project: Path) -> dict[str, str]:
    opened = client.post("/api/vnext/workspaces/open", json={
        "path": str(project), "initialize": True, "project_name": project.name,
    })
    assert opened.status_code == 200, opened.text
    workspace = opened.json()["workspace"]
    return {
        "X-Workspace-ID": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }


def test_invalid_idempotency_key_has_stable_error_contract(client, tmp_path: Path):
    headers = open_workspace(client, tmp_path / "invalid-key")
    response = client.post("/api/vnext/player/publish", headers={
        **headers,
        "Idempotency-Key": "contains spaces",
    })

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_idempotency_key"
