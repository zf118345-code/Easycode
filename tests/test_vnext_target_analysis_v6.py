from __future__ import annotations

import numpy as np

from core.vnext.target_runtime import AndroidAdbTargetDriver, TargetDriver, WindowsTargetDriver


def test_ocr_frame_adapter_returns_record_and_implicit_calls_take_new_frames(monkeypatch):
    from core.vision import ocr_engine as ocr_recognition

    calls: list[bool] = []

    def recognize(_image):
        calls.append(True)
        return ocr_recognition.OcrAdapterResult(
            engine_type="rapidocr",
            text="累计登录福利",
            lines=(
                ocr_recognition.OcrAdapterLine(
                    text="累计登录福利", region=(0, 0, 40, 20)
                ),
            ),
        )

    monkeypatch.setattr(ocr_recognition, "ocr_engine_recognize_detailed", recognize)

    class Driver(TargetDriver):
        def __init__(self):
            self.frame = np.zeros((20, 40, 3), dtype=np.uint8)
            self.platform = "windows"
            self.frame_is_bgr = True
            self.target = {"target_id": "target.test", "space_version": "space.test"}
            self._ocr_frame_cache = {}
            self._ocr_analysis_cache = {}
            self._frame_references = {}
            self._frame_sequence = 0
            self._last_message = ""

        def capture_frame(self):
            return self.frame

    driver = Driver()
    first = driver.execute("text.recognize", {}, lambda: False)
    assert first["ocr_result.field.text"] == "累计登录福利"
    assert "累计登录福利" in driver.consume_message()
    second = driver.execute("text.recognize", {}, lambda: False)
    assert second["ocr_result.field.text"] == "累计登录福利"
    assert len(calls) == 2


def test_windows_uia_and_adb_uiautomator_claim_shared_control_contract(monkeypatch):
    from core.services import uia_service

    monkeypatch.setattr(
        uia_service,
        "find_control",
        lambda **_kwargs: {"name": "确定", "rect": [0, 0, 10, 10]},
    )
    monkeypatch.setattr(
        uia_service,
        "perform_uia_action",
        lambda _info, action, **_kwargs: {
            "ok": True, "value": "已完成", "message": f"UIA {action}",
        },
    )
    driver = object.__new__(WindowsTargetDriver)
    driver.hwnd = 1
    driver.target = {
        "target_id": "target.windows",
        "window_title": "测试",
        "work_area": {"mode": "client"},
        "allow_physical_fallback": True,
    }
    driver._last_message = ""
    driver._control_references = {}
    driver._window_references = {}
    driver._actual_window_title = lambda: "测试"

    reference = driver.execute(
        "control.find",
        {
            "official.control.find.parameter.selector": {
                "control_selector.field.name": "确定",
            },
        },
        lambda: False,
    )
    value = driver.execute(
        "control.read_text",
        {"official.control.read_text.parameter.control": reference},
        lambda: False,
    )

    assert value == "已完成"
    assert "UIA get_text" in driver.consume_message()
    assert WindowsTargetDriver.supports("control.click") is True
    assert AndroidAdbTargetDriver.supports("control.click") is True
