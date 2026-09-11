"""Project-scoped IDE state for format-6 ProgramDocuments."""

from __future__ import annotations

import json
import os
from typing import Any

from .program_repository import ProgramDocumentRepository
from .program_validation import iter_statement_tree
from .workspace_context import VNextWorkspaceContext, VNextWorkspaceError


class VNextIdeService:
    def __init__(self, owner: Any, context: VNextWorkspaceContext) -> None:
        self._owner = owner
        self._context = context

    @staticmethod
    def _debug_path(project_path: str) -> str:
        return os.path.join(project_path, ".easycode", "debug.json")

    @staticmethod
    def _view_state_path(project_path: str) -> str:
        return os.path.join(project_path, ".easycode", "view-state.json")

    @staticmethod
    def _default_view_state() -> dict[str, Any]:
        return {
            'schema_version': 1,
            'active_view': 'program',
            'active_function_id': '',
            'collapsed_statement_ids': {},
            'scroll_offsets': {},
            'panel_sizes': {},
        }

    @staticmethod
    def _documents(project_path: str):
        repository = ProgramDocumentRepository(project_path)
        if not repository.functions_path.is_dir():
            return []
        return [
            repository.load(path.stem).document
            for path in sorted(repository.functions_path.glob("*.json"), key=lambda item: item.name.casefold())
        ]

    @classmethod
    def _statement_ids(cls, project_path: str) -> dict[str, set[str]]:
        return {
            document.function.function_id: {
                statement.statement_id
                for statement in iter_statement_tree(document.function.statements)
            }
            for document in cls._documents(project_path)
        }

    def debug_settings(self, workspace_id: str, generation: int) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        path = self._debug_path(workspace.project_path)
        if not os.path.isfile(path):
            return {"schema_version": 2, "breakpoints": {}}
        value = self._owner._read_json(path)
        breakpoints = value.get("breakpoints") if isinstance(value.get("breakpoints"), dict) else {}
        statement_ids = self._statement_ids(workspace.project_path)
        normalized: dict[str, list[str]] = {}
        for raw_function_id, raw_items in breakpoints.items():
            function_id = str(raw_function_id or "")
            valid = statement_ids.get(function_id)
            if valid is None or not isinstance(raw_items, list):
                continue
            items = sorted({str(item) for item in raw_items if str(item) in valid})
            if items:
                normalized[function_id] = items
        return {"schema_version": 2, "breakpoints": normalized}

    def save_debug_settings(
        self,
        workspace_id: str,
        generation: int,
        breakpoints: dict[str, list[str]],
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        known = self._statement_ids(workspace.project_path)
        normalized: dict[str, list[str]] = {}
        total = 0
        for raw_function_id, raw_items in breakpoints.items():
            function_id = str(raw_function_id or "").strip()
            if function_id not in known:
                raise VNextWorkspaceError(f"项目函数不存在：{function_id or '空 ID'}")
            items = sorted({str(item).strip() for item in raw_items if str(item).strip()})
            unknown = sorted(set(items) - known[function_id])
            if unknown:
                raise VNextWorkspaceError(
                    f"项目函数 {function_id} 不包含语句：{'、'.join(unknown[:5])}"
                )
            if len(items) > 10_000:
                raise VNextWorkspaceError(f"单个项目函数断点数量过多：{function_id}")
            if items:
                normalized[function_id] = items
                total += len(items)
        if total > 50_000:
            raise VNextWorkspaceError("项目断点总数超过 50000")
        result = {"schema_version": 2, "breakpoints": normalized}
        self._owner._atomic_write_json(self._debug_path(workspace.project_path), result)
        return result

    def view_state(self, workspace_id: str, generation: int) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        path = self._view_state_path(workspace.project_path)
        if not os.path.isfile(path):
            return self._default_view_state()
        try:
            raw = self._owner._read_json(path)
        except VNextWorkspaceError:
            return self._default_view_state()
        known = self._statement_ids(workspace.project_path)
        active_function_id = str(raw.get('active_function_id') or '')
        if active_function_id not in known:
            active_function_id = ''
        allowed_views = {'program', 'resources', 'variables', 'targets', 'replay', 'extensions', 'schedules', 'player'}
        active_view = str(raw.get('active_view') or 'program')
        if active_view not in allowed_views:
            active_view = 'program'
        collapsed: dict[str, list[str]] = {}
        collapsed_raw = raw.get('collapsed_statement_ids')
        if not isinstance(collapsed_raw, dict):
            collapsed_raw = {}
        for function_id, items in collapsed_raw.items():
            if function_id not in known or not isinstance(items, list):
                continue
            valid = sorted({str(item) for item in items if str(item) in known[function_id]})
            if valid:
                collapsed[function_id] = valid
        def bounded_map(name: str, maximum: int) -> dict[str, int]:
            value = raw.get(name)
            if not isinstance(value, dict):
                return {}
            return {
                str(key)[:160]: max(0, min(int(number), maximum))
                for key, number in value.items()
                if isinstance(number, int) and not isinstance(number, bool)
            }
        return {
            'schema_version': 1,
            'active_view': active_view,
            'active_function_id': active_function_id,
            'collapsed_statement_ids': collapsed,
            'scroll_offsets': bounded_map('scroll_offsets', 10_000_000),
            'panel_sizes': bounded_map('panel_sizes', 10_000),
        }

    def save_view_state(
        self,
        workspace_id: str,
        generation: int,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation, writable=True)
        # Write the requested state first, then read through the same sanitizer so
        # stale statement IDs and invalid dimensions can never become authority.
        candidate = {'schema_version': 1, **value}
        self._owner._atomic_write_json(self._view_state_path(workspace.project_path), candidate)
        normalized = self.view_state(workspace_id, generation)
        if normalized != candidate:
            self._owner._atomic_write_json(self._view_state_path(workspace.project_path), normalized)
        return normalized

    @staticmethod
    def _search_text(statement: Any) -> str:
        raw = statement.model_dump(mode="json")

        def strip_identity(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: strip_identity(child)
                    for key, child in value.items()
                    if not key.endswith("_id") and key not in {"value_id", "author_review_fingerprint"}
                }
            if isinstance(value, list):
                return [strip_identity(child) for child in value]
            return value

        return json.dumps(strip_identity(raw), ensure_ascii=False, sort_keys=True, default=str)

    def search(
        self,
        workspace_id: str,
        generation: int,
        query: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:
        workspace = self._context.require(workspace_id, generation)
        needle = str(query or "").strip()
        if not needle:
            return {"query": "", "results": [], "truncated": False}
        limit = max(1, min(int(limit), 1000))
        folded = needle.casefold()
        results: list[dict[str, Any]] = []
        truncated = False

        def append_result(document: Any, statement: Any | None, preview: str, index: int) -> bool:
            nonlocal truncated
            if len(results) >= limit:
                truncated = True
                return False
            column = preview.casefold().find(folded)
            results.append({
                "kind": "program",
                "path": document.function.function_id,
                "function_id": document.function.function_id,
                "statement_id": statement.statement_id if statement is not None else "",
                "line": max(1, index),
                "column": max(0, column) + 1,
                "end_column": max(0, column) + len(needle) + 1,
                "preview": preview,
            })
            return True

        for document in self._documents(workspace.project_path):
            function_name = document.function.display_name
            if folded in function_name.casefold() and not append_result(document, None, function_name, 1):
                break
            for index, statement in enumerate(iter_statement_tree(document.function.statements), 1):
                searchable = self._search_text(statement)
                if folded not in searchable.casefold():
                    continue
                preview = str(statement.step_label or "").strip() or searchable[:500]
                if not append_result(document, statement, preview, index):
                    break
            if truncated:
                break
        return {"query": needle, "results": results, "truncated": truncated}


__all__ = ["VNextIdeService"]
