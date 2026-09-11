from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from core.vnext.extensions import VNextExtensionRegistry
from core.vnext.workspace import VNextWorkspaceManager
from scripts.manage_first_party_extension import SPECS, build_source_package, install


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("EASYCODE_EXTENSION_STATE_DIR", str(tmp_path / "extension-state"))
    monkeypatch.setenv("EASYCODE_SIGNING_KEY_DIR", str(tmp_path / "signing-keys"))
    monkeypatch.setenv("EASYCODE_USER_EXTENSIONS_DIR", str(tmp_path / "user-extensions"))
    monkeypatch.setenv("EASYCODE_OFFICIAL_EXTENSIONS_DIR", str(tmp_path / "official-extensions"))
    destination = tmp_path / "destination"
    VNextWorkspaceManager().open(str(destination), initialize=True)
    return destination


@pytest.mark.parametrize("package_key", ["browser", "excel"])
def test_first_party_packages_use_signed_manual_import_lifecycle(project: Path, tmp_path: Path, package_key: str) -> None:
    spec = SPECS[package_key]
    source = build_source_package(spec, tmp_path / f"external-{package_key}")
    imported = VNextExtensionRegistry.import_package(str(project), source_path=str(source), scope="project")

    assert imported["package"]["signature_verified"] is True
    assert imported["package"]["trusted"] is False
    assert imported["package"]["enabled"] is False

    VNextExtensionRegistry.trust(str(project), spec.package_id, "project", mode="explicit")
    VNextExtensionRegistry.build_sealed(str(project), spec.package_id, "project")
    VNextExtensionRegistry.enable(str(project), spec.package_id, "project")
    functions, errors = VNextExtensionRegistry.definitions(str(project))
    assert errors == []
    assert {item["function_id"] for item in functions if item.get("package_id") == spec.package_id} == {
        item["function_id"] for item in spec.contracts
    }
    closure = VNextExtensionRegistry.publish_closure(str(project))
    assert closure["errors"] == []
    assert [item["lock"]["package_id"] for item in closure["packages"]] == [spec.package_id]


def _load_source(path: Path):
    spec = importlib.util.spec_from_file_location("extension_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tabular_package_reads_and_atomically_writes_csv(tmp_path: Path) -> None:
    source = build_source_package(SPECS["excel"], tmp_path / "author")
    module = _load_source(source / "src" / "main.py")
    target = tmp_path / "数据.csv"

    written = module.write_csv(None, str(target), [["name", "count"], ["apple", 2]], "utf-8-sig", ",")
    result = module.read_csv(None, str(target), "utf-8-sig", ",", True)

    assert written["row_count"] == 2
    assert result == {"headers": ["name", "count"], "rows": [["apple", "2"]], "row_count": 1}
    assert not list(tmp_path.glob(".easycode-csv-*"))


def test_tabular_package_reads_minimal_xlsx(tmp_path: Path) -> None:
    source = build_source_package(SPECS["excel"], tmp_path / "author-xlsx")
    module = _load_source(source / "src" / "main.py")
    workbook = tmp_path / "sample.xlsx"
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="inlineStr"><is><t>Name</t></is></c></row><row><c><v>42</v></c></row></sheetData></worksheet>')
    # Numeric cells are supported in the minimal dependency-free reader.
    assert module.list_sheets(None, str(workbook)) == ["Data"]
    assert module.read_xlsx(None, str(workbook), "Data", False)["rows"][-1] == ["42"]

    generated = tmp_path / "generated.xlsx"
    module.write_xlsx(None, str(generated), [["name", "count"], ["apple", 2]], "Report")
    assert module.list_sheets(None, str(generated)) == ["Report"]
    assert module.read_xlsx(None, str(generated), "Report", True)["rows"] == [["apple", "2"]]
    assert not list(tmp_path.glob(".easycode-xlsx-*"))


def test_install_helper_preserves_real_package_boundary(project: Path) -> None:
    result = install(project, SPECS["browser"], "project")
    assert result["imported"] is True
    assert result["signature_verified"] is True
    assert result["enabled"] is True
    assert result["sealed_formats"] == ["ecx-runtime-1"]
    lock = json.loads((project / "easycode.lock").read_text(encoding="utf-8"))
    assert lock["extensions"][0]["package_id"] == SPECS["browser"].package_id
