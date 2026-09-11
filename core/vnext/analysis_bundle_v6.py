"""Immutable, content-addressed inputs and reports for offline replay.

An analysis is only reproducible when it records the bytes that actually took
part in the run.  Paths, current project revisions, and package names are not
substitutes for those bytes.  This module snapshots inputs; it never mutates a
recording frame or ProgramDocument.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException

from core.security import atomic_write_json

from .function_contracts_v6 import official_function_registry_v6
from .recording_storage_v6 import (
    ANALYSIS_DIRECTORY,
    ANALYSIS_INPUT_DIRECTORY,
    RecordingStorageV6,
    canonical_json_bytes,
    sha256_bytes,
)


ANALYSIS_INPUT_FORMAT = 1
ANALYSIS_REPORT_FORMAT = 1
_MODEL_SUFFIXES = frozenset({".onnx", ".bin", ".param", ".txt", ".json", ".yaml", ".yml"})
_MAX_SINGLE_COMPONENT = 2 * 1024 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


def _safe_name(value: str) -> str:
    rendered = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    return rendered[:180] or "component"


class AnalysisInputBundleService:
    """Create immutable input bundles and append-only analysis reports."""

    @classmethod
    def _component(
        cls,
        category: str,
        logical_name: str,
        content: bytes,
        media_type: str,
    ) -> tuple[dict[str, Any], bytes]:
        if len(content) > _MAX_SINGLE_COMPONENT:
            raise HTTPException(status_code=413, detail=f"分析输入过大：{logical_name}")
        digest = sha256_bytes(content)
        suffix = Path(logical_name).suffix[:16]
        relative = f"components/{category}/{digest}{suffix}"
        return ({
            "category": category,
            "logical_name": logical_name,
            "path": relative,
            "sha256": digest,
            "bytes": len(content),
            "media_type": media_type,
        }, content)

    @classmethod
    def _program_components(cls, project_path: str, ecir: dict[str, Any]) -> list[tuple[dict[str, Any], bytes]]:
        project = Path(project_path).resolve()
        function_ids = {
            str(item.get("function_id") or "")
            for item in (ecir.get("functions") or [])
            if isinstance(item, dict) and str(item.get("function_id") or "")
        }
        components: list[tuple[dict[str, Any], bytes]] = []
        function_root = (project / "program" / "functions").resolve()
        for function_id in sorted(function_ids):
            candidate = (function_root / f"{function_id}.json").resolve()
            if function_root not in candidate.parents or not candidate.is_file():
                continue
            components.append(cls._component(
                "program", f"program/functions/{candidate.name}", candidate.read_bytes(), "application/json",
            ))
        # Project variables participate in expression evaluation and therefore
        # are program inputs even when the ECIR contains only their IDs.
        variables = project / "program" / "project-variables.json"
        if variables.is_file():
            components.append(cls._component(
                "program", "program/project-variables.json", variables.read_bytes(), "application/json",
            ))
        return components

    @classmethod
    def _resource_components(cls, project_path: str, ecir: dict[str, Any]) -> list[tuple[dict[str, Any], bytes]]:
        project = Path(project_path).resolve()
        registry_path = project / "assets" / "registry.json"
        try:
            registry_bytes = registry_path.read_bytes()
            registry = json.loads(registry_bytes.decode("utf-8-sig"))
        except (OSError, ValueError, TypeError):
            registry_bytes, registry = b"", {}
        references = {
            str(item.get("asset_id") or "")
            for item in _walk(ecir)
            if isinstance(item, dict) and item.get("kind") == "asset_ref" and item.get("asset_id")
        }
        components: list[tuple[dict[str, Any], bytes]] = []
        if references and registry_bytes:
            components.append(cls._component(
                "resources", "assets/registry.json", registry_bytes, "application/json",
            ))
        assets = registry.get("assets") if isinstance(registry, dict) else {}
        assets = assets if isinstance(assets, dict) else {}
        for asset_id in sorted(references):
            entry = assets.get(asset_id)
            if not isinstance(entry, dict):
                raise HTTPException(status_code=422, detail=f"分析依赖的图片资源不存在：{asset_id}")
            relative = str(entry.get("path") or "").replace("\\", "/").strip("/")
            candidate = (project / relative).resolve()
            if project not in candidate.parents or not candidate.is_file() or candidate.is_symlink():
                raise HTTPException(status_code=422, detail=f"分析依赖的图片资源文件无效：{asset_id}")
            components.append(cls._component(
                "resources", relative, candidate.read_bytes(), "application/octet-stream",
            ))
        return components

    @classmethod
    def _contract_components(cls, function_ids: Iterable[str]) -> list[tuple[dict[str, Any], bytes]]:
        components = []
        for function_id in sorted(set(str(item) for item in function_ids)):
            try:
                value = official_function_registry_v6.require(function_id).to_dict()
            except KeyError as exc:
                raise HTTPException(status_code=422, detail=f"回放函数不是官方契约：{function_id}") from exc
            components.append(cls._component(
                "implementation", f"official-contracts/{function_id}.json",
                canonical_json_bytes(value), "application/json",
            ))
        return components

    @classmethod
    def _ocr_components(cls, enabled: bool) -> tuple[list[tuple[dict[str, Any], bytes]], dict[str, Any]]:
        if not enabled:
            return [], {"required": False, "engines": []}
        components: list[tuple[dict[str, Any], bytes]] = []
        engines = []
        for package in ("rapidocr_onnxruntime", "ddddocr"):
            spec = importlib.util.find_spec(package)
            if spec is None:
                engines.append({"package": package, "available": False})
                continue
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = "unknown"
            entry = {"package": package, "available": True, "version": version, "models": []}
            roots = []
            if spec.submodule_search_locations:
                roots.extend(Path(item).resolve() for item in spec.submodule_search_locations)
            elif spec.origin:
                roots.append(Path(spec.origin).resolve().parent)
            for root in roots:
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in _MODEL_SUFFIXES:
                        continue
                    logical = f"ocr/{package}/{path.relative_to(root).as_posix()}"
                    component = cls._component("ocr", logical, path.read_bytes(), "application/octet-stream")
                    components.append(component)
                    entry["models"].append({
                        "logical_name": logical,
                        "sha256": component[0]["sha256"],
                        "bytes": component[0]["bytes"],
                    })
            engines.append(entry)
        metadata = {"required": True, "engines": engines}
        components.append(cls._component(
            "ocr", "ocr/dependencies.json", canonical_json_bytes(metadata), "application/json",
        ))
        return components, metadata

    @classmethod
    def _implementation_components(
        cls, *, include_ocr: bool,
    ) -> list[tuple[dict[str, Any], bytes]]:
        current = Path(__file__).resolve().parent
        components = []
        for name in (
            "replay.py", "analysis_bundle_v6.py", "vision_analysis_v6.py", "target_runtime.py",
        ):
            path = current / name
            if path.is_file():
                components.append(cls._component(
                    "implementation", f"core/vnext/{name}", path.read_bytes(), "text/x-python",
                ))
        ocr_path = current.parent / "node_executors" / "base" / "ocr_recognition.py"
        if include_ocr and ocr_path.is_file():
            components.append(cls._component(
                "implementation", "core/node_executors/base/ocr_recognition.py",
                ocr_path.read_bytes(), "text/x-python",
            ))
        environment = {
            "python": sys.version,
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
            "packages": {},
        }
        for package in ("Pillow", "numpy", "opencv-python", "rapidocr_onnxruntime", "ddddocr"):
            with contextlib.suppress(importlib.metadata.PackageNotFoundError):
                environment["packages"][package] = importlib.metadata.version(package)
        components.append(cls._component(
            "implementation", "runtime-environment.json", canonical_json_bytes(environment), "application/json",
        ))
        return components

    @classmethod
    def create(
        cls,
        project_path: str,
        ecir: dict[str, Any],
        session_id: str,
        frame_indexes: Iterable[int],
        *,
        analysis_calls: list[dict[str, Any]],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        root = RecordingStorageV6.recordings_root(project_path) / ANALYSIS_INPUT_DIRECTORY
        root.mkdir(parents=True, exist_ok=True)
        all_components: list[tuple[dict[str, Any], bytes]] = []
        frame_records = []
        for index in sorted(set(int(item) for item in frame_indexes)):
            frame = RecordingStorageV6.resolve_frame(project_path, session_id, index)
            RecordingStorageV6.require_frame_integrity(frame)
            logical = f"recordings/{session_id}/frames/{frame.path.name}"
            component = cls._component("frames", logical, frame.path.read_bytes(), "image/png")
            all_components.append(component)
            frame_records.append({
                "frame_id": str(frame.record.get("frame_id") or ""),
                "sequence": int(frame.record.get("sequence") or frame.record.get("index") or index),
                "sha256": component[0]["sha256"],
                "recording_segment_id": str(frame.record.get("recording_segment_id") or ""),
                "target_id": str(frame.record.get("target_id") or ""),
                "space_version": str(frame.record.get("space_version") or ""),
                "component_path": component[0]["path"],
            })
        if not frame_records:
            raise HTTPException(status_code=422, detail="分析输入至少需要一个真实录制帧")
        all_components.extend(cls._program_components(project_path, ecir))
        all_components.append(cls._component("ecir", "ecir.json", canonical_json_bytes(ecir), "application/json"))
        resource_components = cls._resource_components(project_path, ecir)
        all_components.extend(resource_components)
        function_ids = [str(item.get("function_id") or "") for item in analysis_calls]
        all_components.extend(cls._contract_components(function_ids))
        ocr_components, ocr_metadata = cls._ocr_components("official.text.recognize" in function_ids)
        all_components.extend(ocr_components)
        lock = Path(project_path) / "easycode.lock"
        all_components.append(cls._component(
            "parameters", "easycode.lock", lock.read_bytes() if lock.is_file() else b"{}\n", "application/json",
        ))
        all_components.append(cls._component(
            "parameters", "analysis-parameters.json", canonical_json_bytes(parameters), "application/json",
        ))
        all_components.extend(cls._implementation_components(
            include_ocr="official.text.recognize" in function_ids,
        ))

        # Deduplicate identical category/path components before hashing the
        # descriptor.  The descriptor excludes timestamps so the same inputs
        # always produce exactly the same AIB ID.
        unique: dict[tuple[str, str], tuple[dict[str, Any], bytes]] = {}
        for descriptor, content in all_components:
            unique[(descriptor["category"], descriptor["logical_name"])] = (descriptor, content)
        ordered = sorted(unique.values(), key=lambda item: (item[0]["category"], item[0]["logical_name"]))
        categories = sorted({item[0]["category"] for item in ordered})
        required_categories = ["frames", "program", "ecir", "parameters", "implementation"]
        if resource_components:
            required_categories.append("resources")
        if "official.text.recognize" in function_ids:
            required_categories.append("ocr")
        reproducibility = "complete"
        if ocr_metadata.get("required") and not any(item.get("available") for item in ocr_metadata.get("engines") or []):
            reproducibility = "incomplete_missing_ocr_engine"
        descriptor = {
            "analysis_input_format": ANALYSIS_INPUT_FORMAT,
            "recording_session_id": session_id,
            "frames": frame_records,
            "ecir_revision": str(ecir.get("ecir_revision") or ""),
            "entry_function_id": str(ecir.get("entry_function_id") or ""),
            "components": [item[0] for item in ordered],
            "categories": categories,
            "required_categories": required_categories,
            "reproducibility": reproducibility,
        }
        digest = sha256_bytes(canonical_json_bytes(descriptor))
        bundle_id = f"aib_{digest}"
        destination = root / bundle_id
        if destination.is_dir():
            existing = RecordingStorageV6.read_json(destination / "manifest.json", None)
            if not isinstance(existing, dict) or str(existing.get("content_digest")) != digest:
                raise HTTPException(status_code=409, detail="内容寻址分析输入包发生冲突")
            return existing
        temporary = root / f".{bundle_id}.{uuid.uuid4().hex}.tmp"
        temporary.mkdir(parents=False)
        try:
            for component, content in ordered:
                target = temporary / component["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_file():
                    if sha256_bytes(target.read_bytes()) != component["sha256"]:
                        raise HTTPException(status_code=409, detail="分析输入组件哈希冲突")
                    continue
                with target.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            manifest = {
                **descriptor,
                "analysis_input_bundle_id": bundle_id,
                "content_digest": digest,
                "created_at": _utc_now(),
                "immutable": True,
            }
            atomic_write_json(str(temporary / "manifest.json"), manifest, clean_transient=False)
            os.replace(temporary, destination)
            return manifest
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)

    @classmethod
    def write_report(
        cls,
        project_path: str,
        session_id: str,
        input_bundle: dict[str, Any],
        *,
        scope: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        session_dir = RecordingStorageV6.session_dir(project_path, session_id)
        reports = RecordingStorageV6.list_analysis_reports(project_path, session_id)
        previous = next((item for item in reports if item.get("scope") == scope), None)
        run_id = f"analysis_{uuid.uuid4().hex}"
        report = {
            "analysis_report_format": ANALYSIS_REPORT_FORMAT,
            "analysis_run_id": run_id,
            "recording_session_id": session_id,
            "analysis_input_bundle_id": input_bundle["analysis_input_bundle_id"],
            "input_content_digest": input_bundle["content_digest"],
            "created_at": _utc_now(),
            "scope": scope,
            "previous_analysis_run_id": previous.get("analysis_run_id") if previous else None,
            "reproducibility": input_bundle.get("reproducibility"),
            "result": result,
            "immutable": True,
        }
        root = session_dir / ANALYSIS_DIRECTORY
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{run_id}.json"
        if path.exists():
            raise HTTPException(status_code=409, detail="分析报告 ID 冲突")
        atomic_write_json(str(path), report, clean_transient=False)
        return report

    @classmethod
    def bundle_path(
        cls, project_path: str, analysis_input_bundle_id: str,
    ) -> Path:
        bundle_id = str(analysis_input_bundle_id or "")
        if not bundle_id.startswith("aib_") or len(bundle_id) != 68:
            raise HTTPException(status_code=422, detail="分析输入包标识无效")
        root = (RecordingStorageV6.recordings_root(project_path) / ANALYSIS_INPUT_DIRECTORY).resolve()
        path = (root / bundle_id).resolve()
        if root not in path.parents or not path.is_dir():
            raise HTTPException(status_code=404, detail="分析输入包不存在")
        return path

    @classmethod
    def component_path(
        cls,
        project_path: str,
        input_bundle: dict[str, Any],
        relative_path: str,
    ) -> Path:
        root = cls.bundle_path(project_path, str(input_bundle.get("analysis_input_bundle_id") or ""))
        parts = tuple(item for item in str(relative_path or "").replace("\\", "/").split("/") if item)
        if not parts or any(item in {".", ".."} for item in parts):
            raise HTTPException(status_code=422, detail="分析输入组件路径无效")
        path = root.joinpath(*parts).resolve()
        if root not in path.parents or not path.is_file() or path.is_symlink():
            raise HTTPException(status_code=422, detail="分析输入组件缺失")
        return path


analysis_input_bundle_service = AnalysisInputBundleService()


__all__ = ["AnalysisInputBundleService", "analysis_input_bundle_service"]
