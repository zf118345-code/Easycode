"""Project-wide, confirmed ControlSelectorV2 reference repair."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

from .mutation import ProjectMutationTransaction
from .program_repository import ProgramDocumentRepository
from .program_serialization import canonical_json_bytes, content_revision
from .program_types import ProgramDocument
from .program_validation import validate_program_document


class ControlSelectorRepairError(RuntimeError):
    def __init__(self, error_id: str, message: str) -> None:
        super().__init__(message)
        self.error_id = error_id


def _literal_value(value: Any) -> str:
    return str(value.get("value") or "") if isinstance(value, dict) and value.get("kind") in {"literal", "string"} else ""


def _selector_id(record: Any) -> str:
    if not isinstance(record, dict) or record.get("kind") != "record" or record.get("record_type") != "control_selector":
        return ""
    return _literal_value((record.get("fields") or {}).get("control_selector.field.selector_id"))


def _visit(value: Any, selector_id: str, *, replace_with: dict[str, Any] | None = None) -> tuple[Any, list[dict[str, str]]]:
    references: list[dict[str, str]] = []
    if isinstance(value, list):
        result = []
        for item in value:
            next_item, found = _visit(item, selector_id, replace_with=replace_with)
            result.append(next_item)
            references.extend(found)
        return result, references
    if not isinstance(value, dict):
        return value, references
    if _selector_id(value) == selector_id:
        references.append({
            "statement_id": str(value.get("_owner_statement_id") or ""),
            "value_id": str(value.get("value_id") or ""),
        })
        if replace_with is not None:
            replacement = copy.deepcopy(replace_with)
            replacement["value_id"] = value.get("value_id")
            replacement.setdefault("fields", {}).setdefault(
                "control_selector.field.selector_id",
                {"value_id": f"value_{uuid.uuid4().hex}", "kind": "string", "value": selector_id},
            )["value"] = selector_id

            def unique_ids(node: Any, root: bool = False) -> None:
                if isinstance(node, dict):
                    if not root and "value_id" in node:
                        node["value_id"] = f"value_{uuid.uuid4().hex}"
                    for child in node.values():
                        unique_ids(child)
                elif isinstance(node, list):
                    for child in node:
                        unique_ids(child)

            unique_ids(replacement, root=True)
            return replacement, references
    result: dict[str, Any] = {}
    owner = str(value.get("statement_id") or value.get("_owner_statement_id") or "")
    for key, item in value.items():
        candidate = item
        if owner and isinstance(candidate, dict):
            candidate = {**candidate, "_owner_statement_id": owner}
        next_item, found = _visit(candidate, selector_id, replace_with=replace_with)
        if isinstance(next_item, dict):
            next_item.pop("_owner_statement_id", None)
        result[key] = next_item
        references.extend(found)
    return result, references


class ControlSelectorRepairService:
    def references(self, project_path: str, selector_id: str) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        root = Path(project_path).resolve() / "program" / "functions"
        for path in sorted(root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            _unchanged, found = _visit(payload, selector_id)
            for reference in found:
                result.append({"function_id": path.stem, **reference})
        return result

    def repair(
        self,
        project_path: str,
        selector_id: str,
        replacement: dict[str, Any],
        *,
        expected_revisions: dict[str, str],
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise ControlSelectorRepairError("control.repair_confirmation_required", "批量修复前必须确认受影响引用")
        if _selector_id(replacement) not in {"", selector_id}:
            raise ControlSelectorRepairError("control.selector_identity_mismatch", "重新捕获结果属于另一控件身份")
        if replacement.get("kind") != "record" or replacement.get("record_type") != "control_selector":
            raise ControlSelectorRepairError("control.selector_invalid", "重新捕获结果不是控件选择器")
        root = Path(project_path).resolve()
        replacements: dict[str, bytes] = {}
        references: list[dict[str, str]] = []
        for path in sorted((root / "program" / "functions").glob("*.json")):
            content = path.read_bytes()
            payload = json.loads(content.decode("utf-8"))
            updated, found = _visit(payload, selector_id, replace_with=replacement)
            if not found:
                continue
            actual_revision = content_revision(content)
            if expected_revisions.get(path.stem) != actual_revision:
                raise ControlSelectorRepairError("control.repair_revision_conflict", f"函数 {path.stem} 已变化，请重新检查引用")
            document = ProgramDocument.model_validate(updated)
            diagnostics = validate_program_document(document)
            if diagnostics:
                raise ControlSelectorRepairError("control.repair_invalid", diagnostics[0].message)
            replacements[path.relative_to(root).as_posix()] = canonical_json_bytes(document)
            references.extend({"function_id": path.stem, **item} for item in found)
        if not replacements:
            raise ControlSelectorRepairError("control.repair_reference_missing", "项目中没有找到该控件引用")
        transaction_id = ProjectMutationTransaction.apply(str(root), replacements)
        ProgramDocumentRepository.clear_snapshot_cache()
        return {"transaction_id": transaction_id, "updated_count": len(references), "references": references}


control_selector_repair_service = ControlSelectorRepairService()

__all__ = ["ControlSelectorRepairError", "ControlSelectorRepairService", "control_selector_repair_service"]
