# core/conditions/handlers/text_contains.py
import cv2
import pyautogui
import numpy as np
from typing import Any
from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register("text_contains")
class TextContainsEvaluator(BaseConditionEvaluator):

    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        raw_text = str(params.get("target_text", "")).strip()
        operator = str(params.get("exist_mode") or params.get("operator", "contains"))
        gray_scale = bool(params.get("gray_scale", True))
        gray_threshold = int(params.get("gray_threshold", 127))

        if not raw_text:
            return False

        # ⚡ 调取工业级变量引擎解析目标文本
        target_text = resolve_template_string(raw_text, context)

        try:
            screen = pyautogui.screenshot()
            frame_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

            if gray_scale:
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
                processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            else:
                processed_img = frame_bgr

            from core.node_executors.base.ocr_recognition import get_ocr_engine
            engine_type, ocr_engine = get_ocr_engine()

            detected_text = ""
            if engine_type == "ddddocr" and ocr_engine:
                _, img_bytes = cv2.imencode('.png', processed_img)
                raw_res = ocr_engine.classification(img_bytes.tobytes())
                detected_text = str(raw_res).strip() if raw_res else ""

            if operator in ("contains", "exists"):
                return target_text in detected_text
            elif operator in ("not_contains", "not_exists"):
                return target_text not in detected_text
            elif operator == "exact":
                return target_text == detected_text

        except Exception as e:
            if hasattr(context, 'log'):
                context.log(f"⚠️ [OCR 判定失败]: {e}", "warning")
            return False

        return False