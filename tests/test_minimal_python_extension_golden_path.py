from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router
from core.vnext.extensions import VNextExtensionRegistry
from core.vnext.workspace import VNextWorkspaceManager
from scripts.manage_minimal_python_extension import FUNCTION_ID, PACKAGE_ID, build_source_package, install, remove


@pytest.fixture
def extension_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("EASYCODE_EXTENSION_STATE_DIR", str(tmp_path / "extension-state"))
    monkeypatch.setenv("EASYCODE_SIGNING_KEY_DIR", str(tmp_path / "signing-keys"))
    monkeypatch.setenv("EASYCODE_USER_EXTENSIONS_DIR", str(tmp_path / "user-extensions"))
    monkeypatch.setenv("EASYCODE_OFFICIAL_EXTENSIONS_DIR", str(tmp_path / "official-extensions"))
    project = tmp_path / "destination-project"
    VNextWorkspaceManager().open(str(project), initialize=True)
    return project


@pytest.mark.parametrize("scope", ["project", "user"])
def test_minimal_python_package_uses_real_import_lifecycle(extension_environment: Path, scope: str) -> None:
    project = extension_environment
    result = install(project, scope)

    assert result["imported"] is True
    assert result["signature_verified"] is True
    assert result["trusted"] is True
    assert result["sealed_formats"] == ["ecx-runtime-1"]
    assert result["enabled"] is True
    assert result["lock_current"] is True
    assert result["contract_tests"]["passed"] is True
    assert result["catalog_function_ids"] == [FUNCTION_ID]
    assert result["catalog_errors"] == []

    package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, scope)
    assert package["scope"] == scope
    lock = json.loads((project / "easycode.lock").read_text(encoding="utf-8"))
    assert [item["package_id"] for item in lock["extensions"]] == [PACKAGE_ID]

    assert remove(project, scope) == {"package_id": PACKAGE_ID, "scope": scope, "removed": True}
    assert PACKAGE_ID not in (project / "project.json").read_text(encoding="utf-8")
    assert PACKAGE_ID not in (project / "easycode.lock").read_text(encoding="utf-8")


def test_http_import_matches_ui_and_does_not_auto_trust_or_enable(
    extension_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = extension_environment
    manager = VNextWorkspaceManager()
    opened = manager.open(str(project))
    workspace = opened["workspace"]
    assert workspace is not None
    source = build_source_package(tmp_path / "external-package")

    monkeypatch.setattr("api.routers.vnext_router.vnext_workspace_manager", manager)
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    response = client.post(
        "/api/vnext/extensions/import",
        headers={
            "X-Workspace-Id": workspace["workspace_id"],
            "X-Workspace-Generation": str(workspace["generation"]),
        },
        json={"source_path": str(source), "scope": "project"},
    )
    assert response.status_code == 200, response.text
    package = response.json()["package"]
    assert package["signature_verified"] is True
    assert package["trusted"] is False
    assert package["enabled"] is False
    assert package["lock_current"] is False
