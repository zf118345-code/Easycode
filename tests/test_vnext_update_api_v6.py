from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_player_update_router import create_vnext_player_update_router
from api.routers.vnext_router import create_vnext_router
from api.routers.vnext_update_router import create_vnext_update_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    app.include_router(create_vnext_update_router())
    return TestClient(app)


def _open(client: TestClient, project: Path) -> dict[str, str]:
    response = client.post(
        "/api/vnext/workspaces/open",
        json={"path": str(project), "initialize": True, "project_name": "更新 API 测试"},
    )
    assert response.status_code == 200, response.text
    workspace = response.json()["workspace"]
    return {
        "X-Workspace-ID": workspace["workspace_id"],
        "X-Workspace-Generation": str(workspace["generation"]),
    }


def _domain(enabled: bool, product_id: str = "", feed: str = "") -> dict:
    return {
        "enabled": enabled,
        "product_id": product_id,
        "provider": "self_hosted",
        "feed_base_url": feed,
        "channel": "stable",
        "required_policy_capability": enabled,
        "initial_preferences": {
            "automatic_check": True,
            "automatic_download": False,
            "automatic_apply": False,
        },
        "pinned_root": None,
    }


def test_standalone_player_update_router_contains_no_author_or_ide_routes() -> None:
    router = create_vnext_player_update_router()

    api_paths = {route.path for route in router.routes}
    assert api_paths == {
        "/api/vnext/player/runtime/updates",
        "/api/vnext/player/runtime/updates/apply",
        "/api/vnext/player/runtime/updates/check",
        "/api/vnext/player/runtime/updates/download",
        "/api/vnext/player/runtime/updates/preferences",
        "/api/vnext/player/runtime/updates/reset-group",
        "/api/vnext/player/runtime/updates/safe-point",
        "/api/vnext/player/runtime/updates/{domain}/group-code",
    }
    assert not any("configuration" in path or "/ide/" in path or "/releases/" in path for path in api_paths)


def test_author_configuration_and_static_repository_initialization(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("EASYCODE_SIGNING_KEY_DIR", str(tmp_path / "author-keys"))
    monkeypatch.setenv("EASYCODE_UPDATE_SIGNING_KEY_DIR", str(tmp_path / "update-keys"))
    client = _client()
    headers = _open(client, tmp_path / "project")
    initial = client.get("/api/vnext/updates/configuration", headers=headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["enabled"] is False

    configuration = {
        "schema_version": 1,
        "domains": {
            "player_application": _domain(False),
            "project_content": _domain(
                True,
                "content.api.test",
                "https://updates.example.test/feed/content.api.test/project_content",
            ),
        },
    }
    saved = client.put("/api/vnext/updates/configuration", headers=headers, json=configuration)
    assert saved.status_code == 200, saved.text
    feed_root = tmp_path / "static-feed"
    initialized = client.post(
        "/api/vnext/updates/repository/initialize",
        headers=headers,
        json={"domain": "project_content", "repository_root": str(feed_root)},
    )
    assert initialized.status_code == 200, initialized.text
    assert (feed_root / "content.api.test" / "project_content" / "metadata" / "root.json").is_file()
    after = client.get("/api/vnext/updates/configuration", headers=headers).json()
    assert after["configuration"]["domains"]["project_content"]["pinned_root"]["signed"]["product_id"] == "content.api.test"


def test_official_hosting_is_never_faked_when_provider_is_unavailable(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("EASYCODE_SIGNING_KEY_DIR", str(tmp_path / "author-keys"))
    monkeypatch.setenv("EASYCODE_UPDATE_SIGNING_KEY_DIR", str(tmp_path / "update-keys"))
    # An environment toggle must never turn the local static publisher into a
    # fake official account/upload service.
    monkeypatch.setenv("EASYCODE_OFFICIAL_UPDATE_PROVIDER_AVAILABLE", "true")
    client = _client()
    headers = _open(client, tmp_path / "project")
    content = _domain(True, "content.official.test", "https://updates.example.test/content")
    content["provider"] = "easycode_hosted"
    response = client.put(
        "/api/vnext/updates/configuration",
        headers=headers,
        json={"schema_version": 1, "domains": {"player_application": _domain(False), "project_content": content}},
    )
    assert response.status_code == 200

    initialized = client.post(
        "/api/vnext/updates/repository/initialize",
        headers=headers,
        json={"domain": "project_content", "repository_root": str(tmp_path / "feed")},
    )

    assert initialized.status_code == 409
    assert "未连接真实 EasyCode 官方托管" in initialized.json()["detail"]["message"]


def test_disabled_configuration_rejects_hidden_endpoint_or_policy(tmp_path: Path) -> None:
    client = _client()
    headers = _open(client, tmp_path / "project")
    invalid = _domain(False)
    invalid["feed_base_url"] = "https://should-not-be-packed.example"
    invalid["required_policy_capability"] = True

    response = client.put(
        "/api/vnext/updates/configuration",
        headers=headers,
        json={"schema_version": 1, "domains": {"player_application": invalid, "project_content": _domain(False)}},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UPD-CONFIG-002"
