from __future__ import annotations

from pathlib import Path

from core.vnext.extensions import VNextExtensionRegistry
from core.vnext.workspace import VNextWorkspaceManager
from scripts.manage_extension_showcase import PACKAGE_ID, install, remove


def test_showcase_installs_calls_and_removes_cleanly(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EASYCODE_EXTENSION_STATE_DIR", str(tmp_path / "extension-state"))
    monkeypatch.setenv("EASYCODE_SIGNING_KEY_DIR", str(tmp_path / "signing-keys"))
    monkeypatch.setenv("EASYCODE_USER_EXTENSIONS_DIR", str(tmp_path / "user-extensions"))
    monkeypatch.setenv("EASYCODE_OFFICIAL_EXTENSIONS_DIR", str(tmp_path / "official-extensions"))
    project = tmp_path / "project"
    opened = VNextWorkspaceManager().open(str(project), initialize=True)
    assert opened["workspace"] is not None

    result = install(project)
    assert result["enabled"] is True
    assert result["contract_tests"]["passed"] is True
    assert len(result["catalog_function_ids"]) == 3
    package = VNextExtensionRegistry.package(str(project), PACKAGE_ID, "project")
    assert package["enabled"] is True
    workspace_contribution = next(item for item in package["contributions"] if item["kind"] == "workspaces")
    assert workspace_contribution["workspaces"] == [f"{PACKAGE_ID}.workspace.main"]

    assert remove(project) == {"package_id": PACKAGE_ID, "removed": True}
    assert not (project / "extensions" / PACKAGE_ID).exists()
    assert PACKAGE_ID not in (project / "project.json").read_text(encoding="utf-8")
    assert PACKAGE_ID not in (project / "easycode.lock").read_text(encoding="utf-8")
