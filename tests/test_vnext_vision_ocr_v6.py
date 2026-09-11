from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from core.vision.ocr_engine import OcrAdapterLine, OcrAdapterResult
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_commands import insert_call
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_types import create_program_document
from core.vnext.record_types_v6 import record_catalog_payload, record_type_contract
from core.vnext.replay import VNextReplayService
from core.vnext.runtime import RuntimeFailure
from core.vnext.target_runtime import TargetDriver


def _project_with_asset(tmp_path: Path) -> tuple[Path, str, np.ndarray]:
    project = tmp_path / "project"
    image_dir = project / "assets" / "image"
    image_dir.mkdir(parents=True)
    asset_id = "asset.template"
    rng = np.random.default_rng(12345)
    template = rng.integers(20, 240, size=(7, 9, 3), dtype=np.uint8)
    asset_bytes_path = image_dir / f"{asset_id}.png"
    Image.fromarray(template, mode="RGB").save(asset_bytes_path)
    content = asset_bytes_path.read_bytes()
    registry = {
        "schema_version": 1,
        "folders": {"image": [], "ocr": [], "page": []},
        "assets": {
            asset_id: {
                "asset_id": asset_id,
                "display_name": "测试模板",
                "category": "image",
                "folder": "",
                "path": f"assets/image/{asset_id}.png",
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        },
    }
    (project / "assets" / "registry.json").write_text(
        json.dumps(registry, ensure_ascii=False), encoding="utf-8"
    )
    return project, asset_id, template


def _frame(template: np.ndarray, *locations: tuple[int, int]) -> np.ndarray:
    frame = np.zeros((48, 72, 3), dtype=np.uint8)
    height, width = template.shape[:2]
    for x, y in locations:
        frame[y : y + height, x : x + width] = template
    return frame


class _SyntheticDriver(TargetDriver):
    def __init__(self, project: Path, frames: list[np.ndarray], *, bgr: bool = False) -> None:
        self.platform = "android_adb" if bgr else "windows"
        self.frame_is_bgr = bgr
        self._frames = [item.copy() for item in frames]
        self.capture_count = 0
        super().__init__(str(project), {
            "target_id": f"target.{self.platform}",
            "type": self.platform,
            "space_version": "space.v1",
        })

    def capture_frame(self):
        index = min(self.capture_count, len(self._frames) - 1)
        self.capture_count += 1
        return self._frames[index].copy()

    def tap_point(self, x, y, button):  # pragma: no cover - not used here
        raise AssertionError("unexpected input")

    def input_text(self, arguments, cancelled):  # pragma: no cover - not used here
        raise AssertionError("unexpected input")

    def scroll(self, arguments, cancelled):  # pragma: no cover - not used here
        raise AssertionError("unexpected input")

    def drag_path(self, arguments, cancelled):  # pragma: no cover - not used here
        raise AssertionError("unexpected input")

    def press_key(self, keys, action, hold_ms, cancelled):  # pragma: no cover - not used here
        raise AssertionError("unexpected input")


def _asset_ref(asset_id: str) -> dict[str, str]:
    return {"kind": "asset_ref", "asset_id": asset_id}


def _region(x: int, y: int, width: int, height: int) -> dict[str, int | str]:
    return {"kind": "rect", "x": x, "y": y, "width": width, "height": height}


def test_record_catalog_has_stable_vision_and_ocr_fields() -> None:
    image_match = record_type_contract("image_match")
    assert image_match is not None
    assert [item.field_id for item in image_match.fields] == [
        "image_match.field.region",
        "image_match.field.center",
        "image_match.field.similarity",
        "image_match.field.source_asset",
        "image_match.field.source_frame",
        "image_match.field.source_target",
        "image_match.field.space_version",
    ]
    payload = record_catalog_payload()
    type_ids = [item["type_id"] for item in payload]
    assert len(type_ids) == len(set(type_ids))
    assert {"color", "frame_ref", "image_match", "ocr_line", "ocr_result"} <= set(type_ids)


@pytest.mark.parametrize(
    ("region", "actual"),
    (
        ([-3, 2, 10, 8], [0, 2, 7, 8]),
        ([5, -4, 10, 8], [5, 0, 10, 4]),
        ([68, 2, 10, 8], [68, 2, 4, 8]),
        ([5, 44, 10, 8], [5, 44, 10, 4]),
    ),
    ids=["left", "top", "right", "bottom"],
)
def test_analysis_crop_clamps_each_frame_edge(region: list[int], actual: list[int]) -> None:
    frame = np.zeros((48, 72, 3), dtype=np.uint8)
    cropped, offset_x, offset_y, metadata = TargetDriver._analysis_crop(frame, region)

    assert cropped is not None
    assert list(cropped.shape[:2]) == [actual[3], actual[2]]
    assert [offset_x, offset_y] == actual[:2]
    assert metadata == {
        "requested_region": region,
        "actual_region": actual,
        "region_clipped": True,
        "region_empty": False,
    }


def test_visible_vision_contracts_insert_and_compile_with_typed_defaults() -> None:
    document = create_program_document("视觉测试")
    for function_id in (
        "official.image.find_all",
        "official.text.recognize",
    ):
        document = insert_call(
            document, official_function_registry_v6, function_id
        ).document
    compiled = compile_program_document(
        document,
        official_function_registry_v6,
        target_platform="windows",
    )
    # The required image remains deliberately unset, but OCR's complete record
    # default itself must be type-valid and lowerable.
    assert any(item["code"] == "PGM-VALUE-001" for item in compiled["diagnostics"])
    assert not any(
        "ocr_preprocess" in item["message"] and item["code"] != "PGM-VALUE-001"
        for item in compiled["diagnostics"]
    )


@pytest.mark.parametrize("bgr", [False, True], ids=["windows-rgb", "adb-bgr"])
def test_find_all_uses_real_region_crop_and_bounded_results(tmp_path: Path, bgr: bool) -> None:
    project, asset_id, template = _project_with_asset(tmp_path)
    rgb = _frame(template, (4, 5), (40, 28))
    source = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if bgr else rgb
    driver = _SyntheticDriver(project, [source] * 3, bgr=bgr)

    matches = driver.execute("vision.find_all", {
        "official.image.find_all.parameter.image": _asset_ref(asset_id),
        "official.image.find_all.parameter.similarity": 0.99,
        "official.image.find_all.parameter.region": _region(30, 20, 35, 25),
        "official.image.find_all.parameter.limit": 10,
    }, lambda: False)

    assert len(matches) == 1
    assert matches[0]["image_match.field.region"] == _region(40, 28, 9, 7)
    assert matches[0]["image_match.field.center"] == {"kind": "point", "x": 44, "y": 31}
    assert matches[0]["image_match.field.source_asset"] == _asset_ref(asset_id)
    assert matches[0]["image_match.field.source_target"]["target_id"] == f"target.{driver.platform}"
    assert matches[0]["image_match.field.space_version"] == "space.v1"

    limited = driver.execute("vision.find_all", {
        "official.image.find_all.parameter.image": _asset_ref(asset_id),
        "official.image.find_all.parameter.similarity": 0.99,
        "official.image.find_all.parameter.limit": 1,
    }, lambda: False)
    assert len(limited) == 1
    assert driver.capture_count == 2


def test_explicit_frame_reuses_pixels_and_implicit_calls_capture_new_frames(
    tmp_path: Path,
) -> None:
    project, asset_id, template = _project_with_asset(tmp_path)
    populated = _frame(template, (4, 5))
    blank = np.zeros_like(populated)
    driver = _SyntheticDriver(project, [populated, blank, blank])
    frame_reference = driver.execute("target.capture_frame", {}, lambda: False)

    find_arguments = {
        "official.image.find.parameter.image": _asset_ref(asset_id),
        "official.image.find.parameter.similarity": 0.99,
        "official.image.find.parameter.frame": frame_reference,
    }
    first = driver.execute("vision.find", find_arguments, lambda: False)
    second = driver.execute("vision.find", find_arguments, lambda: False)
    assert first == second
    assert driver.capture_count == 1
    assert first["image_match.field.source_frame"] == frame_reference
    assert frame_reference["frame_ref.field.width"] == 72
    assert frame_reference["frame_ref.field.height"] == 48

    implicit = {
        "official.image.find.parameter.image": _asset_ref(asset_id),
        "official.image.find.parameter.similarity": 0.99,
    }
    assert driver.execute("vision.find", implicit, lambda: False) is None
    assert driver.execute("vision.find", implicit, lambda: False) is None
    assert driver.capture_count == 3


def test_find_miss_reports_the_real_best_similarity_and_threshold(tmp_path: Path) -> None:
    project, asset_id, template = _project_with_asset(tmp_path)
    near_match = _frame(template, (4, 5))
    near_match[5, 4] = np.array([0, 0, 0], dtype=np.uint8)
    driver = _SyntheticDriver(project, [near_match])

    result = driver.execute('vision.find', {
        'official.image.find.parameter.image': _asset_ref(asset_id),
        'official.image.find.parameter.similarity': 0.99999,
    }, lambda: False)
    diagnostic = driver.image_match_diagnostic()
    message = driver.consume_message()

    assert result is None
    assert 0 < diagnostic['best_similarity'] < diagnostic['threshold']
    assert '未命中' in message
    assert f"最高相似度 {diagnostic['best_similarity']:.3f}" in message
    assert '阈值 1.000' in message


@pytest.mark.parametrize("bgr", [False, True], ids=["windows-rgb", "adb-bgr"])
def test_analysis_regions_clip_to_the_current_frame_instead_of_failing(
    tmp_path: Path,
    bgr: bool,
) -> None:
    project, asset_id, template = _project_with_asset(tmp_path)
    rgb = _frame(template, (60, 40))
    source = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if bgr else rgb
    driver = _SyntheticDriver(project, [source] * 4, bgr=bgr)

    match = driver.execute("vision.find", {
        "official.image.find.parameter.image": _asset_ref(asset_id),
        "official.image.find.parameter.similarity": 0.99,
        # The captured 30x20 region was valid on a slightly larger frame.  On
        # this 72x48 frame its usable intersection is 17x13.
        "official.image.find.parameter.region": _region(55, 35, 30, 20),
    }, lambda: False)
    assert match is not None
    assert match["image_match.field.region"] == _region(60, 40, 9, 7)
    diagnostic = driver.image_match_diagnostic()
    assert diagnostic["requested_region"] == [55, 35, 30, 20]
    assert diagnostic["actual_region"] == [55, 35, 17, 13]
    assert diagnostic["region_clipped"] is True
    assert "已按当前画面裁剪" in driver.consume_message()

    color = driver.execute("color.find", {
        "official.color.find.parameter.color": {
            "color.field.red": int(rgb[40, 60, 0]),
            "color.field.green": int(rgb[40, 60, 1]),
            "color.field.blue": int(rgb[40, 60, 2]),
            "color.field.alpha": 255,
        },
        "official.color.find.parameter.tolerance": 0,
        "official.color.find.parameter.region": _region(60, 40, 30, 20),
    }, lambda: False)
    assert color == {"kind": "point", "x": 60, "y": 40}
    assert "已按当前画面裁剪" in driver.consume_message()

    missing = driver.execute("vision.find", {
        "official.image.find.parameter.image": _asset_ref(asset_id),
        "official.image.find.parameter.similarity": 0.99,
        "official.image.find.parameter.region": _region(90, 70, 20, 20),
    }, lambda: False)
    assert missing is None
    assert driver.image_match_diagnostic()["region_empty"] is True
    assert "搜索区域与当前画面无交集" in driver.consume_message()

    missing_color = driver.execute("color.find", {
        "official.color.find.parameter.color": {
            "color.field.red": 0,
            "color.field.green": 0,
            "color.field.blue": 0,
            "color.field.alpha": 255,
        },
        "official.color.find.parameter.tolerance": 0,
        "official.color.find.parameter.region": _region(90, 70, 20, 20),
    }, lambda: False)
    assert missing_color is None
    assert "搜索区域与当前画面无交集" in driver.consume_message()


def test_ocr_returns_fixed_record_caches_same_explicit_frame_and_logs_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.vision import ocr_engine as ocr_recognition

    project, _, template = _project_with_asset(tmp_path)
    driver = _SyntheticDriver(project, [_frame(template)])
    frame_reference = driver.execute("target.capture_frame", {}, lambda: False)
    calls: list[tuple[int, int]] = []

    def recognize(image_bgr):
        calls.append(image_bgr.shape[:2])
        return OcrAdapterResult(
            engine_type="rapidocr",
            text="登录\n成功",
            lines=(
                OcrAdapterLine(text="登录", region=(1, 2, 10, 5)),
                OcrAdapterLine(text="成功", region=(1, 9, 10, 5)),
            ),
        )

    monkeypatch.setattr(ocr_recognition, "ocr_engine_recognize_detailed", recognize)
    arguments = {
        "official.text.recognize.parameter.region": _region(10, 12, 30, 20),
        "official.text.recognize.parameter.language": "auto",
        "official.text.recognize.parameter.frame": frame_reference,
        "official.text.recognize.parameter.preprocess": {
            "ocr_preprocess.field.grayscale": True,
            "ocr_preprocess.field.binary": True,
            "ocr_preprocess.field.threshold": 160,
            "ocr_preprocess.field.invert": False,
        },
    }

    first = driver.execute("text.recognize", arguments, lambda: False)
    second = driver.execute("text.recognize", arguments, lambda: False)
    assert first == second
    assert calls == [(20, 30)]
    assert first["ocr_result.field.text"] == "登录\n成功"
    assert first["ocr_result.field.region"] == _region(10, 12, 30, 20)
    assert first["ocr_result.field.lines"][0]["ocr_line.field.region"] == _region(11, 14, 10, 5)
    assert first["ocr_result.field.source_frame"] == frame_reference
    message = driver.consume_message()
    assert "登录" in message and "区域=[10, 12, 30, 20]" in message
    assert "置信度" not in message
    assert driver.capture_count == 1

    changed_preprocess = {
        **arguments,
        "official.text.recognize.parameter.preprocess": {
            **arguments["official.text.recognize.parameter.preprocess"],
            "ocr_preprocess.field.threshold": 161,
        },
    }
    driver.execute("text.recognize", changed_preprocess, lambda: False)
    assert calls == [(20, 30), (20, 30)]


def test_ocr_no_text_is_normal_empty_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.vision import ocr_engine as ocr_recognition

    project, _, template = _project_with_asset(tmp_path)
    driver = _SyntheticDriver(project, [_frame(template)])
    monkeypatch.setattr(
        ocr_recognition,
        "ocr_engine_recognize_detailed",
        lambda _image: OcrAdapterResult(engine_type="ddddocr", text="", lines=()),
    )
    result = driver.execute("text.recognize", {}, lambda: False)
    assert result["ocr_result.field.text"] == ""
    assert result["ocr_result.field.lines"] == []
    assert result["ocr_result.field.region"] == _region(0, 0, 72, 48)
    assert "未识别到有效文字" in driver.consume_message()


def test_ocr_region_clips_and_no_overlap_skips_the_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.vision import ocr_engine as ocr_recognition

    project, _, template = _project_with_asset(tmp_path)
    driver = _SyntheticDriver(project, [_frame(template)] * 2)
    calls: list[tuple[int, int]] = []

    def recognize(image_bgr):
        calls.append(image_bgr.shape[:2])
        return OcrAdapterResult(
            engine_type="rapidocr",
            text="边缘文字",
            lines=(OcrAdapterLine(text="边缘文字", region=(1, 1, 6, 4)),),
        )

    monkeypatch.setattr(ocr_recognition, "ocr_engine_recognize_detailed", recognize)
    clipped = driver.execute("text.recognize", {
        "official.text.recognize.parameter.region": _region(60, 40, 20, 20),
    }, lambda: False)
    assert calls == [(8, 12)]
    assert clipped["ocr_result.field.region"] == _region(60, 40, 12, 8)
    assert clipped["ocr_result.field.lines"][0]["ocr_line.field.region"] == _region(61, 41, 6, 4)
    assert "已按当前画面裁剪" in driver.consume_message()

    outside = driver.execute("text.recognize", {
        "official.text.recognize.parameter.region": _region(90, 70, 20, 20),
    }, lambda: False)
    assert calls == [(8, 12)]
    assert outside["ocr_result.field.text"] == ""
    assert outside["ocr_result.field.lines"] == []
    assert outside["ocr_result.field.region"] == _region(72, 48, 0, 0)
    assert "搜索区域与当前画面无交集" in driver.consume_message()


def test_vision_and_ocr_failures_are_structured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.vision import ocr_engine as ocr_recognition

    project, asset_id, template = _project_with_asset(tmp_path)
    driver = _SyntheticDriver(project, [_frame(template)])
    with pytest.raises(RuntimeFailure) as missing:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref("asset.missing"),
        }, lambda: False)
    assert missing.value.error_id == "vision.asset_missing"

    with pytest.raises(RuntimeFailure) as legacy_argument:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref(asset_id),
            "相似度": 0.9,
        }, lambda: False)
    assert legacy_argument.value.error_id == "runtime.argument_type"

    with pytest.raises(RuntimeFailure) as similarity:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref(asset_id),
            "official.image.find.parameter.similarity": 1.1,
        }, lambda: False)
    assert similarity.value.error_id == "vision.similarity_invalid"

    with pytest.raises(RuntimeFailure) as limit:
        driver.execute("vision.find_all", {
            "official.image.find_all.parameter.image": _asset_ref(asset_id),
            "official.image.find_all.parameter.limit": 1001,
        }, lambda: False)
    assert limit.value.error_id == "vision.limit_invalid"

    with pytest.raises(RuntimeFailure) as region:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref(asset_id),
            "official.image.find.parameter.region": _region(10, 10, 0, 10),
        }, lambda: False)
    assert region.value.error_id == "vision.region_invalid"

    with pytest.raises(RuntimeFailure) as expired:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref(asset_id),
            "official.image.find.parameter.frame": {
                "kind": "frame_ref",
                "frame_ref.field.frame_id": "frame.expired",
            },
        }, lambda: False)
    assert expired.value.error_id == "vision.frame_reference_expired"

    (project / "assets" / "image" / f"{asset_id}.png").write_bytes(b"tampered")
    with pytest.raises(RuntimeFailure) as corrupt:
        driver.execute("vision.find", {
            "official.image.find.parameter.image": _asset_ref(asset_id),
        }, lambda: False)
    assert corrupt.value.error_id == "vision.asset_corrupt"

    def unavailable(_image):
        raise ocr_recognition.OcrAdapterError(
            "没有 OCR 引擎", reason="engine_unavailable"
        )

    monkeypatch.setattr(ocr_recognition, "ocr_engine_recognize_detailed", unavailable)
    with pytest.raises(RuntimeFailure) as ocr:
        driver.execute("text.recognize", {}, lambda: False)
    assert ocr.value.error_id == "ocr.engine_unavailable"


def test_rapidocr_and_ddddocr_share_structured_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.vision import ocr_engine as ocr_recognition

    image = np.zeros((20, 30, 3), dtype=np.uint8)

    class Rapid:
        def __call__(self, _image):
            return ([[[1, 2], [11, 2], [11, 8], [1, 8]], "文字", 0.99],), None

    monkeypatch.setattr(ocr_recognition, "_ENGINE_TYPE", "rapidocr")
    monkeypatch.setattr(ocr_recognition, "_OCR_ENGINE", Rapid())
    rapid = ocr_recognition.ocr_engine_recognize_detailed(image)
    assert rapid.text == "文字"
    assert rapid.lines[0].region == (1, 2, 10, 6)

    class Dddd:
        def classification(self, _content):
            return "验证码"

    monkeypatch.setattr(ocr_recognition, "_ENGINE_TYPE", "ddddocr")
    monkeypatch.setattr(ocr_recognition, "_OCR_ENGINE", Dddd())
    dddd = ocr_recognition.ocr_engine_recognize_detailed(image)
    assert dddd.text == "验证码"
    assert dddd.lines[0].region == (0, 0, 30, 20)


def test_replay_has_dedicated_find_all_and_ocr_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.vision import ocr_engine as ocr_recognition

    project, asset_id, template = _project_with_asset(tmp_path)
    frame = Image.fromarray(_frame(template, (4, 5), (40, 28)), mode="RGB")
    driver = TargetDriver(str(project), {"type": "offline_replay"})
    registry = json.loads((project / "assets" / "registry.json").read_text(encoding="utf-8"))
    driver._replay_asset_paths = {
        asset_id: project / registry["assets"][asset_id]["path"],
    }
    common = {
        "owner_function_id": "function.main",
        "instruction_id": "statement.test",
        "analysis_id": "function.main:statement.test",
        "display_name": "图像.查找全部",
    }
    image_result = VNextReplayService._analyze_call(driver, frame, {
        **common,
        "function_id": "official.image.find_all",
        "arguments": {
            "official.image.find_all.parameter.image": _asset_ref(asset_id),
            "official.image.find_all.parameter.similarity": 0.99,
            "official.image.find_all.parameter.region": None,
            "official.image.find_all.parameter.frame": None,
            "official.image.find_all.parameter.limit": 10,
        },
    })
    assert "error" not in image_result
    assert image_result["matched"] is True
    assert image_result["match_count"] == 2

    monkeypatch.setattr(
        ocr_recognition,
        "ocr_engine_recognize_detailed",
        lambda _image: OcrAdapterResult(
            engine_type="rapidocr",
            text="离线识别",
            lines=(OcrAdapterLine(text="离线识别", region=(2, 3, 20, 6)),),
        ),
    )
    ocr_result = VNextReplayService._analyze_call(driver, frame, {
        **common,
        "instruction_id": "statement.ocr",
        "analysis_id": "function.main:statement.ocr",
        "display_name": "文字.识别",
        "function_id": "official.text.recognize",
        "arguments": {
            "official.text.recognize.parameter.region": _region(10, 10, 30, 20),
            "official.text.recognize.parameter.language": "auto",
            "official.text.recognize.parameter.frame": None,
            "official.text.recognize.parameter.preprocess": {},
        },
    })
    assert ocr_result["text"] == "离线识别"
    assert ocr_result["region"] == [10, 10, 30, 20]
    assert ocr_result["lines"][0]["region"] == [12, 13, 20, 6]

    clipped_image = VNextReplayService._analyze_call(driver, frame, {
        **common,
        "instruction_id": "statement.clipped-image",
        "analysis_id": "function.main:statement.clipped-image",
        "function_id": "official.image.find",
        "display_name": "图像.查找",
        "arguments": {
            "official.image.find.parameter.image": _asset_ref(asset_id),
            "official.image.find.parameter.similarity": 0.99,
            "official.image.find.parameter.region": _region(35, 25, 50, 30),
            "official.image.find.parameter.frame": None,
        },
    })
    assert clipped_image["matched"] is True
    assert clipped_image["actual_region"] == [35, 25, 37, 23]
    assert clipped_image["region_clipped"] is True

    outside_ocr = VNextReplayService._analyze_call(driver, frame, {
        **common,
        "instruction_id": "statement.outside-ocr",
        "analysis_id": "function.main:statement.outside-ocr",
        "display_name": "文字.识别",
        "function_id": "official.text.recognize",
        "arguments": {
            "official.text.recognize.parameter.region": _region(90, 70, 20, 20),
            "official.text.recognize.parameter.language": "auto",
            "official.text.recognize.parameter.frame": None,
            "official.text.recognize.parameter.preprocess": {},
        },
    })
    assert outside_ocr["matched"] is False
    assert outside_ocr["text"] == ""
    assert outside_ocr["region"] == [72, 48, 0, 0]
    assert outside_ocr["region_clipped"] is True


def test_windows_player_spec_collects_ocr_models_and_onnx_runtime() -> None:
    from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

    spec = (Path(__file__).resolve().parents[1] / "scripts" / "player.spec").read_text(
        encoding="utf-8"
    )
    assert "collect_data_files('rapidocr_onnxruntime')" in spec
    assert "collect_data_files('ddddocr')" in spec
    assert "collect_dynamic_libs('onnxruntime')" in spec
    rapid_data = collect_data_files("rapidocr_onnxruntime")
    dddd_data = collect_data_files("ddddocr")
    onnx_binaries = collect_dynamic_libs("onnxruntime")
    assert any(source.endswith(".onnx") for source, _target in rapid_data)
    assert any(source.endswith(".onnx") for source, _target in dddd_data)
    assert any(Path(source).name.lower().startswith("onnxruntime") for source, _target in onnx_binaries)
