"""Offline analysis of recorded frames using format-6 ProgramDocument ECIR.

Replay never revives the retired page topology.  It scans the reachable
ProgramDocument bundle for explicitly replay-safe official calls and executes
only their dedicated, side-effect-free frame adapters.
"""

from __future__ import annotations

import statistics
import time
import json
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException
from PIL import Image

from core.utils import load_image, prepare_template_cv

from .analysis_bundle_v6 import AnalysisInputBundleService
from .recording_storage_v6 import RecordingStorageV6
from .runtime import RuntimeFailure, VNextRuntime
from .target_runtime import TargetDriver
from .vision_analysis_v6 import find_template_matches, frame_to_bgr


class VNextReplayService:
    MAX_ANALYSIS_FRAMES = 10_000
    _REPLAYABLE_FUNCTIONS = frozenset({
        "official.image.find",
        "official.image.find_all",
        "official.text.recognize",
    })
    _REPLAY_DISPLAY_NAMES = {
        "official.image.find": "图像.查找",
        "official.image.find_all": "图像.查找全部",
        "official.text.recognize": "文字.识别",
    }

    @staticmethod
    def list_sessions(project_path: str) -> list[dict[str, Any]]:
        return RecordingStorageV6.list_sessions(project_path)

    @staticmethod
    def list_frames(project_path: str, session_id: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
        return RecordingStorageV6.list_frames(project_path, session_id, offset, limit)

    @staticmethod
    def frame_bytes(project_path: str, session_id: str, frame_index: int) -> tuple[bytes, str]:
        return RecordingStorageV6.frame_bytes(project_path, session_id, frame_index)

    @staticmethod
    def frame_thumbnail_bytes(project_path: str, session_id: str, frame_index: int) -> bytes:
        return RecordingStorageV6.frame_thumbnail_bytes(project_path, session_id, frame_index)

    @staticmethod
    def session_detail(project_path: str, session_id: str) -> dict[str, Any]:
        return RecordingStorageV6.session_detail(project_path, session_id)

    @staticmethod
    def timeline(
        project_path: str, session_id: str, offset: int = 0, limit: int = 500,
    ) -> dict[str, Any]:
        return RecordingStorageV6.timeline(project_path, session_id, offset, limit)

    @staticmethod
    def verify_session(project_path: str, session_id: str) -> dict[str, Any]:
        return RecordingStorageV6.verify_session(project_path, session_id)

    @staticmethod
    def compare_frames(
        project_path: str, session_id: str, left_frame_index: int, right_frame_index: int,
    ) -> dict[str, Any]:
        return RecordingStorageV6.compare_frames(
            project_path, session_id, left_frame_index, right_frame_index,
        )

    @staticmethod
    def comparison_image_bytes(
        project_path: str, session_id: str, left_frame_index: int, right_frame_index: int,
    ) -> bytes:
        return RecordingStorageV6.comparison_image_bytes(
            project_path, session_id, left_frame_index, right_frame_index,
        )

    @staticmethod
    def analysis_reports(project_path: str, session_id: str) -> list[dict[str, Any]]:
        return RecordingStorageV6.list_analysis_reports(project_path, session_id)

    @staticmethod
    def analysis_report(
        project_path: str, session_id: str, analysis_run_id: str,
    ) -> dict[str, Any]:
        return RecordingStorageV6.analysis_report(project_path, session_id, analysis_run_id)

    @staticmethod
    def delete_analysis_report(
        project_path: str, session_id: str, analysis_run_id: str,
    ) -> dict[str, Any]:
        return RecordingStorageV6.delete_analysis_report(project_path, session_id, analysis_run_id)

    @staticmethod
    def create_export(
        project_path: str,
        session_id: str,
        *,
        mode: str,
        analysis_run_ids: Iterable[str] = (),
        include_categories: Iterable[str] = (),
        frame_indices: Iterable[int] = (),
    ) -> dict[str, Any]:
        return RecordingStorageV6.create_export(
            project_path,
            session_id,
            mode=mode,
            analysis_run_ids=analysis_run_ids,
            include_categories=include_categories,
            frame_indices=frame_indices,
        )

    @staticmethod
    def export_path(project_path: str, session_id: str, export_id: str) -> str:
        return str(RecordingStorageV6.export_path(project_path, session_id, export_id))

    @staticmethod
    def delete_session(project_path: str, session_id: str) -> dict[str, Any]:
        return RecordingStorageV6.delete_session(project_path, session_id)

    @staticmethod
    def _walk_instruction_values(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            if value.get("instruction_id") and value.get("opcode"):
                yield value
            for key, child in value.items():
                if key not in {"arguments", "source", "parameter_ids"}:
                    yield from VNextReplayService._walk_instruction_values(child)
        elif isinstance(value, list):
            for child in value:
                yield from VNextReplayService._walk_instruction_values(child)

    @classmethod
    def _replayable_calls(
        cls,
        ecir: dict[str, Any],
        analysis_ids: Iterable[str] | None = None,
        *,
        require_calls: bool = True,
    ) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for function in ecir.get("functions") or []:
            if not isinstance(function, dict):
                continue
            owner_function_id = str(function.get("function_id") or "")
            for instruction in cls._walk_instruction_values(function.get("instructions") or []):
                called_function_id = str(instruction.get("function_id") or "")
                if called_function_id not in cls._REPLAYABLE_FUNCTIONS:
                    continue
                statement_id = str(instruction.get("instruction_id") or "")
                key = (owner_function_id, statement_id)
                if key in seen:
                    continue
                seen.add(key)
                calls.append({
                    **instruction,
                    "owner_function_id": owner_function_id,
                    "analysis_id": f"{owner_function_id}:{statement_id}",
                    "display_name": cls._REPLAY_DISPLAY_NAMES[called_function_id],
                })
        requested = set(str(item) for item in (analysis_ids or ()))
        if requested:
            available = {str(item["analysis_id"]) for item in calls}
            unknown = sorted(requested - available)
            if unknown:
                raise HTTPException(
                    status_code=422,
                    detail=f"分析语句不在当前入口的官方无副作用回放目录中：{', '.join(unknown[:5])}",
                )
            calls = [item for item in calls if item["analysis_id"] in requested]
        if not calls and require_calls:
            raise HTTPException(
                status_code=422,
                detail="当前项目入口的可达函数中没有可回放的官方图像/OCR分析语句",
            )
        return calls

    @classmethod
    def analysis_catalog(cls, ecir: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "analysis_id": item["analysis_id"],
                "function_id": item["function_id"],
                "owner_function_id": item["owner_function_id"],
                "statement_id": str(item.get("instruction_id") or ""),
                "display_name": item["display_name"],
                "side_effect_free": True,
                "implementation": "official_dedicated_adapter",
            }
            for item in cls._replayable_calls(ecir, require_calls=False)
        ]

    @staticmethod
    def _resolved_arguments(instruction: dict[str, Any]) -> dict[str, Any]:
        return {
            str(parameter_id): VNextRuntime._value(value, {})
            for parameter_id, value in (instruction.get("arguments") or {}).items()
        }

    @classmethod
    def _analyze_call(
        cls,
        driver: TargetDriver,
        frame: Image.Image,
        instruction: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        function_id = str(instruction.get("function_id") or "")
        result: dict[str, Any] = {
            "analysis_id": instruction["analysis_id"],
            "function_id": function_id,
            "owner_function_id": instruction["owner_function_id"],
            "statement_id": str(instruction.get("instruction_id") or ""),
            "display_name": instruction["display_name"],
            "matched": False,
        }
        try:
            arguments = cls._resolved_arguments(instruction)
            if function_id in {"official.image.find", "official.image.find_all"}:
                cls._analyze_image_call(driver, frame, function_id, arguments, result)
            elif function_id == "official.text.recognize":
                cls._analyze_ocr_call(driver, frame, arguments, result)
            else:
                raise RuntimeFailure(
                    f"离线回放没有该函数的专用实现：{function_id}",
                    error_id="replay.function_unsupported",
                )
        except (RuntimeFailure, OSError, ValueError, TypeError) as exc:
            result["error"] = str(exc)
            result["error_id"] = str(getattr(exc, "error_id", "") or "replay.analysis_failed")
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return result

    @staticmethod
    def _reject_explicit_replay_frame(arguments: dict[str, Any], owner: str) -> None:
        if arguments.get(f"{owner}.parameter.frame") is not None:
            raise RuntimeFailure(
                "离线回放使用所选录制帧，不接受运行期画面引用",
                error_id="replay.dynamic_argument_unsupported",
            )

    @classmethod
    def _analyze_image_call(
        cls,
        driver: TargetDriver,
        frame: Image.Image,
        function_id: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        driver._reject_unknown_v6_arguments(
            arguments,
            function_id,
            (
                ("image", "similarity", "region", "frame", "limit")
                if function_id == "official.image.find_all"
                else ("image", "similarity", "region", "frame")
            ),
        )
        cls._reject_explicit_replay_frame(arguments, function_id)
        image = arguments.get(f"{function_id}.parameter.image")
        if not isinstance(image, dict) or image.get("kind") != "asset_ref":
            raise RuntimeFailure(
                "离线图像分析要求图片参数为固定资源引用",
                error_id="replay.dynamic_argument_unsupported",
            )
        similarity = driver._v6_similarity(
            arguments.get(f"{function_id}.parameter.similarity", 0.85)
        )
        try:
            region = driver._v6_rect(arguments.get(f"{function_id}.parameter.region"))
        except RuntimeFailure as exc:
            raise RuntimeFailure(str(exc), error_id="vision.region_invalid") from exc
        limit = (
            driver._v6_result_limit(arguments.get(f"{function_id}.parameter.limit", 100))
            if function_id == "official.image.find_all"
            else 1
        )
        variants, source_asset = cls._prepared_replay_asset(driver, image)
        cropped, offset_x, offset_y, crop_meta = driver._analysis_crop(frame, region)
        matches = []
        if cropped is not None:
            try:
                matches = find_template_matches(
                    cropped,
                    variants,
                    threshold=similarity,
                    limit=limit,
                    offset_x=offset_x,
                    offset_y=offset_y,
                    frame_is_bgr=False,
                )
            except Exception as exc:
                raise RuntimeFailure(
                    f"离线图像分析失败：{exc}",
                    error_id="vision.analysis_failed",
                    transient=True,
                ) from exc
        rendered = [
            {
                "score": round(float(match.similarity), 4),
                "center": list(match.center),
                "region": list(match.region),
            }
            for match in matches
        ]
        result.update({
            "matched": bool(rendered),
            "match_count": len(rendered),
            "matches": rendered,
            "asset_id": str(source_asset["asset_id"]),
            "requested_region": crop_meta["requested_region"],
            "actual_region": crop_meta["actual_region"],
            "region_clipped": crop_meta["region_clipped"],
        })
        if function_id == "official.image.find":
            first = rendered[0] if rendered else {}
            result.update({
                "score": first.get("score"),
                "center": first.get("center"),
                "region": first.get("region"),
            })

    @staticmethod
    def _prepared_replay_asset(
        driver: TargetDriver,
        reference: Any,
    ) -> tuple[Any, dict[str, Any]]:
        """Load only the immutable resource bytes frozen in the AIB.

        ``TargetDriver._prepared_v6_asset`` intentionally resolves resources
        from an editable project registry.  Replay must never do that: a
        project asset may have changed after recording or after an earlier
        report.  The AIB builder attaches an exact asset-id -> component map
        to this dedicated adapter instead.
        """

        if not isinstance(reference, dict) or reference.get("kind") != "asset_ref":
            raise RuntimeFailure(
                "离线图像分析要求图片参数为固定资源引用",
                error_id="replay.dynamic_argument_unsupported",
            )
        asset_id = str(reference.get("asset_id") or "").strip()
        paths = getattr(driver, "_replay_asset_paths", {})
        path = paths.get(asset_id) if isinstance(paths, dict) else None
        if path is None:
            raise RuntimeFailure(
                f"分析输入包缺少图片资源：{asset_id or '<empty>'}",
                error_id="vision.asset_missing",
            )
        cache = getattr(driver, "_replay_prepared_asset_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            driver._replay_prepared_asset_cache = cache
        if asset_id not in cache:
            try:
                template = load_image(str(path))
                variants = prepare_template_cv(
                    template,
                    gray_scale=False,
                    scales=(1.0, 0.9, 1.1, 0.75),
                )
            except Exception as exc:
                raise RuntimeFailure(
                    f"分析输入包图片资源无法解码：{exc}",
                    error_id="vision.asset_corrupt",
                ) from exc
            if not variants:
                raise RuntimeFailure(
                    "分析输入包图片资源尺寸过小，无法用于匹配",
                    error_id="vision.asset_corrupt",
                )
            cache[asset_id] = variants
        return cache[asset_id], {"kind": "asset_ref", "asset_id": asset_id}

    @classmethod
    def _analyze_ocr_call(
        cls,
        driver: TargetDriver,
        frame: Image.Image,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        from core.vision.ocr_engine import (
            OcrAdapterError,
            ocr_engine_recognize_detailed,
            preprocess_ocr_image,
        )

        owner = "official.text.recognize"
        driver._reject_unknown_v6_arguments(
            arguments, owner, ("region", "language", "frame", "preprocess")
        )
        cls._reject_explicit_replay_frame(arguments, owner)
        language = str(arguments.get(f"{owner}.parameter.language") or "auto")
        if language != "auto":
            raise RuntimeFailure(
                f"当前 OCR 不支持语言模式：{language}",
                error_id="ocr.language_unsupported",
            )
        preprocess = driver._v6_ocr_preprocess(arguments.get(f"{owner}.parameter.preprocess"))
        try:
            region = driver._v6_rect(arguments.get(f"{owner}.parameter.region"))
        except RuntimeFailure as exc:
            raise RuntimeFailure(str(exc), error_id="vision.region_invalid") from exc
        cropped, offset_x, offset_y, crop_meta = driver._analysis_crop(frame, region)
        if cropped is None:
            actual_region = tuple(crop_meta["actual_region"])
            result.update({
                "matched": False,
                "text": "",
                "lines": [],
                "region": list(actual_region),
                "requested_region": crop_meta["requested_region"],
                "region_clipped": crop_meta["region_clipped"],
            })
            return
        crop_width, crop_height = (int(item) for item in cropped.size)
        actual_region = (offset_x, offset_y, crop_width, crop_height)
        cache_key = (id(frame), actual_region, language, preprocess)
        cached = driver._ocr_analysis_cache.get(cache_key)
        if cached is None:
            grayscale, binary, threshold, invert = preprocess
            try:
                image_bgr = frame_to_bgr(cropped, frame_is_bgr=False)
                prepared = preprocess_ocr_image(
                    image_bgr,
                    gray_scale=grayscale or binary,
                    gray_threshold=threshold,
                    binary=binary,
                    invert=invert,
                )
                recognized = ocr_engine_recognize_detailed(prepared)
            except OcrAdapterError as exc:
                error_id = (
                    "ocr.engine_unavailable"
                    if exc.reason == "engine_unavailable"
                    else "ocr.inference_failed"
                )
                raise RuntimeFailure(
                    str(exc),
                    error_id=error_id,
                    transient=error_id == "ocr.inference_failed",
                ) from exc
            except Exception as exc:
                raise RuntimeFailure(
                    f"离线 OCR 分析失败：{exc}",
                    error_id="ocr.inference_failed",
                    transient=True,
                ) from exc
            cached = {
                "text": recognized.text,
                "lines": [
                    {
                        "text": line.text,
                        "region": [
                            int(line.region[0] + offset_x),
                            int(line.region[1] + offset_y),
                            int(line.region[2]),
                            int(line.region[3]),
                        ],
                    }
                    for line in recognized.lines
                ],
                "region": list(actual_region),
            }
            driver._ocr_analysis_cache[cache_key] = cached
        result.update({
            "matched": bool(cached["text"]),
            "text": cached["text"],
            "lines": cached["lines"],
            "region": cached["region"],
            "requested_region": crop_meta["requested_region"],
            "region_clipped": crop_meta["region_clipped"],
        })

    @classmethod
    def _analyze_image(
        cls,
        project_path: str,
        image: Image.Image,
        calls: list[dict[str, Any]],
        input_bundle: dict[str, Any],
    ) -> list[dict[str, Any]]:
        driver = TargetDriver(project_path, {"type": "offline_replay"})
        try:
            # Use the exact resource bytes frozen in the AIB rather than the
            # possibly newer editable project.  TargetDriver's vetted image
            # preparation remains the only image adapter implementation.
            components = {
                str(item.get("logical_name") or ""): item
                for item in (input_bundle.get("components") or [])
                if isinstance(item, dict)
            }
            registry_component = components.get("assets/registry.json")
            if registry_component:
                registry_path = AnalysisInputBundleService.component_path(
                    project_path, input_bundle, str(registry_component.get("path") or ""),
                )
                registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
                assets = registry.get("assets") if isinstance(registry, dict) else {}
                assets = assets if isinstance(assets, dict) else {}
                frozen_asset_paths = {}
                for asset_id, raw in assets.items():
                    if not isinstance(raw, dict):
                        continue
                    logical = str(raw.get("path") or "").replace("\\", "/").strip("/")
                    component = components.get(logical)
                    if component is None:
                        continue
                    frozen_asset_paths[str(asset_id)] = AnalysisInputBundleService.component_path(
                        project_path, input_bundle, str(component.get("path") or ""),
                    )
                driver._replay_asset_paths = frozen_asset_paths
            return [cls._analyze_call(driver, image, instruction) for instruction in calls]
        finally:
            driver.close()

    @staticmethod
    def _bundle_frame_image(
        project_path: str,
        input_bundle: dict[str, Any],
        frame_index: int,
    ) -> Image.Image:
        frame = next((
            item for item in (input_bundle.get("frames") or [])
            if int(item.get("sequence") or 0) == int(frame_index)
        ), None)
        if not isinstance(frame, dict):
            raise HTTPException(status_code=422, detail="分析输入包缺少选定帧")
        path = AnalysisInputBundleService.component_path(
            project_path, input_bundle, str(frame.get("component_path") or ""),
        )
        try:
            with Image.open(path) as source:
                return source.convert("RGB")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"分析输入包帧无法解码：{exc}") from exc

    @classmethod
    def analyze_frame(
        cls,
        project_path: str,
        ecir: dict[str, Any],
        session_id: str,
        frame_index: int,
        *,
        analysis_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        detail = RecordingStorageV6.session_detail(project_path, session_id)
        if int(detail.get("recording_format") or 0) >= 3:
            verification = RecordingStorageV6.verify_session(project_path, session_id)
            if not verification["ok"]:
                raise HTTPException(status_code=422, detail={
                    "error_id": "replay.recording_integrity_failed",
                    "message": "录制会话完整性校验失败，不能生成可信分析报告",
                    "issues": verification["issues"],
                })
        started = time.perf_counter()
        calls = cls._replayable_calls(ecir, analysis_ids)
        input_bundle = AnalysisInputBundleService.create(
            project_path,
            ecir,
            session_id,
            [frame_index],
            analysis_calls=calls,
            parameters={
                "scope": "frame",
                "frame_index": int(frame_index),
                "analysis_ids": [item["analysis_id"] for item in calls],
            },
        )
        image = cls._bundle_frame_image(project_path, input_bundle, frame_index)
        analyses = cls._analyze_image(project_path, image, calls, input_bundle)
        result = {
            "session_id": session_id,
            "frame_index": int(frame_index),
            "width": image.width,
            "height": image.height,
            "ecir_revision": str(ecir.get("ecir_revision") or ""),
            "entry_function_id": str(ecir.get("entry_function_id") or ""),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "analysis_count": len(analyses),
            "matched_count": sum(1 for item in analyses if item.get("matched")),
            "error_count": sum(1 for item in analyses if item.get("error")),
            "analyses": analyses,
        }
        report = AnalysisInputBundleService.write_report(
            project_path,
            session_id,
            input_bundle,
            scope=f"frame:{int(frame_index)}",
            result=result,
        )
        return {
            **result,
            "analysis_run_id": report["analysis_run_id"],
            "analysis_input_bundle_id": input_bundle["analysis_input_bundle_id"],
            "reproducibility": input_bundle["reproducibility"],
        }

    @classmethod
    def analyze_session(
        cls,
        project_path: str,
        ecir: dict[str, Any],
        session_id: str,
        *,
        changes_only: bool = False,
        change_threshold: float = 0.006,
        step: int = 1,
        max_frames: int = 1_000,
        analysis_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        detail = RecordingStorageV6.session_detail(project_path, session_id)
        if int(detail.get("recording_format") or 0) >= 3:
            verification = RecordingStorageV6.verify_session(project_path, session_id)
            if not verification["ok"]:
                raise HTTPException(status_code=422, detail={
                    "error_id": "replay.recording_integrity_failed",
                    "message": "录制会话完整性校验失败，不能生成可信分析报告",
                    "issues": verification["issues"],
                })
        session_dir = RecordingStorageV6.session_dir(project_path, session_id)
        records, _ = RecordingStorageV6.read_jsonl(session_dir / "frames.jsonl")
        step = max(1, int(step or 1))
        max_frames = max(1, min(cls.MAX_ANALYSIS_FRAMES, int(max_frames or 1_000)))
        selected = []
        for record in records[::step]:
            if changes_only and float(record.get("change_score") or 0.0) < float(change_threshold or 0.006):
                continue
            selected.append(record)
            if len(selected) >= max_frames:
                break
        calls = cls._replayable_calls(ecir, analysis_ids)
        parameters = {
            "scope": "session",
            "changes_only": bool(changes_only),
            "change_threshold": float(change_threshold),
            "step": step,
            "max_frames": max_frames,
            "analysis_ids": [item["analysis_id"] for item in calls],
        }
        selected_indexes = [
            int(item.get("sequence") or item.get("frame_sequence") or item.get("index") or 0)
            for item in selected
        ]
        input_bundle = AnalysisInputBundleService.create(
            project_path,
            ecir,
            session_id,
            selected_indexes,
            analysis_calls=calls,
            parameters=parameters,
        )
        coverage = {
            item["analysis_id"]: {
                "analysis_id": item["analysis_id"],
                "function_id": item["function_id"],
                "owner_function_id": item["owner_function_id"],
                "statement_id": str(item.get("instruction_id") or ""),
                "display_name": item["display_name"],
                "matched_frames": 0,
                "first_frame": None,
            }
            for item in calls
        }
        frames: list[dict[str, Any]] = []
        elapsed_values: list[float] = []
        started = time.perf_counter()
        for record in selected:
            index = int(record.get("sequence") or record.get("frame_sequence") or record.get("index") or 0)
            try:
                image = cls._bundle_frame_image(project_path, input_bundle, index)
                frame_started = time.perf_counter()
                analyses = cls._analyze_image(project_path, image, calls, input_bundle)
                result = {
                    "elapsed_ms": round((time.perf_counter() - frame_started) * 1000, 2),
                    "analyses": analyses,
                    "error_count": sum(1 for item in analyses if item.get("error")),
                }
            except HTTPException as exc:
                frames.append({"frame_index": index, "error": str(exc.detail), "matched_analysis_ids": []})
                continue
            elapsed_values.append(float(result["elapsed_ms"]))
            matched_ids = [
                str(item["analysis_id"])
                for item in result["analyses"]
                if item.get("matched")
            ]
            for analysis_id in matched_ids:
                entry = coverage[analysis_id]
                entry["matched_frames"] += 1
                if entry["first_frame"] is None:
                    entry["first_frame"] = index
            frames.append({
                "frame_index": index,
                "captured_at": record.get("captured_at"),
                "change_score": float(record.get("change_score") or 0.0),
                "elapsed_ms": result["elapsed_ms"],
                "matched_analysis_ids": matched_ids,
                "error_count": result["error_count"],
            })
        ordered = sorted(elapsed_values)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else 0.0
        result = {
            "session_id": session_id,
            "entry_function_id": str(ecir.get("entry_function_id") or ""),
            "ecir_revision": str(ecir.get("ecir_revision") or ""),
            "source_frame_count": len(records),
            "analyzed_frame_count": len(frames),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "frame_analysis_p95_ms": round(p95, 2),
            "average_frame_analysis_ms": round(statistics.fmean(elapsed_values), 2) if elapsed_values else 0.0,
            "unmatched_frame_count": sum(1 for item in frames if not item.get("matched_analysis_ids")),
            "error_frame_count": sum(1 for item in frames if item.get("error") or item.get("error_count")),
            "coverage": list(coverage.values()),
            "frames": frames,
        }
        report = AnalysisInputBundleService.write_report(
            project_path,
            session_id,
            input_bundle,
            scope="session",
            result=result,
        )
        return {
            **result,
            "analysis_run_id": report["analysis_run_id"],
            "analysis_input_bundle_id": input_bundle["analysis_input_bundle_id"],
            "reproducibility": input_bundle["reproducibility"],
        }


vnext_replay_service = VNextReplayService()


__all__ = ["VNextReplayService", "vnext_replay_service"]
