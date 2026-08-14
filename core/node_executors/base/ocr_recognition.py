# core/node_executors/base/ocr_recognition.py
import base64
import os
import time

import cv2
import numpy as np
import pyautogui

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

_DDDD_OCR_ENGINE = None
_ENGINE_TYPE = None


def get_ocr_engine():
    global _DDDD_OCR_ENGINE, _ENGINE_TYPE
    if _ENGINE_TYPE is not None:
        return _ENGINE_TYPE, _DDDD_OCR_ENGINE

    try:
        import ddddocr

        _DDDD_OCR_ENGINE = ddddocr.DdddOcr(show_ad=False)
        _ENGINE_TYPE = 'ddddocr'
        print('✅ [OCR 引擎初始化] ddddocr 启动成功！')
    except Exception as e:
        print(f'❌ [OCR 引擎初始化失败] ddddocr 导入异常: {e}')
        _ENGINE_TYPE = 'none'

    return _ENGINE_TYPE, _DDDD_OCR_ENGINE


def image_to_base64(img_np):
    try:
        _, buffer = cv2.imencode('.png', img_np)
        return 'data:image/png;base64,' + base64.b64encode(buffer).decode('utf-8')
    except Exception:
        return None


@NodeExecutorRegistry.register('ocr_recognition')
class OcrRecognitionNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params

        region_type = params.get('region_type', 'recorded')
        region_value = params.get('region_value', [0, 0, 0, 0])
        timeout = params.get('timeout', 3000) / 1000.0
        gray_scale = params.get('gray_scale', True)
        gray_threshold = params.get('gray_threshold', 127)
        save_to_var = params.get('save_to_var', '').strip()

        engine_type, ocr_engine = get_ocr_engine()

        # ---------------- 🔍 1. 计算识别区域坐标 ----------------
        if (
            region_type in ('recorded', 'custom')
            and len(region_value) == 4
            and region_value[2] > 0
            and region_value[3] > 0
        ):
            x, y, w, h = region_value
            if context.is_window_mode():
                wx, wy, ww, wh = context.get_window_rect()
                x += wx
                y += wy
            region_rect = (int(x), int(y), int(w), int(h))
        else:
            region_rect = context.get_window_rect()

        context.log(f'📋 [OCR 识别定位] 模式: {region_type} | 绝对计算区域: {region_rect}')

        # ---------------- 📸 2. 落盘调试准备 ----------------
        debug_dir = os.path.join(context.project_dir, 'debug_screenshots')
        os.makedirs(debug_dir, exist_ok=True)

        start_time = time.time()
        detected_text = ''
        found = False
        debug_b64 = None
        attempt_count = 0

        # ---------------- 🔄 3. 主识别循环 ----------------
        while time.time() - start_time < timeout:
            attempt_count += 1
            try:
                screenshot = pyautogui.screenshot(region=region_rect)
                frame_rgb = np.array(screenshot)
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                if gray_scale:
                    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
                    processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                else:
                    processed_img = frame_bgr

                if engine_type == 'ddddocr' and ocr_engine:
                    _, img_bytes = cv2.imencode('.png', processed_img)
                    raw_res = ocr_engine.classification(img_bytes.tobytes())
                    detected_text = str(raw_res).strip() if raw_res else ''
                else:
                    detected_text = ''

                debug_b64 = image_to_base64(processed_img)

                if detected_text:
                    found = True
                    break

            except Exception as e:
                context.log(f'💥 [OCR 第 {attempt_count} 次尝试异常]: {e}', 'error')
                break

            time.sleep(0.3)

        # ---------------- 🎯 4. 终局结果处理 ----------------
        extra_data = {}
        if debug_b64:
            extra_data['debug_image'] = debug_b64

        if found:
            context.log(f'🎯 [OCR 识别成功] 最终抓取文本: "{detected_text}"', image=debug_b64)

            if save_to_var:
                context.variables[save_to_var] = detected_text
                context.log(f'📝 [变量写入] context.variables[\'{save_to_var}\'] = "{detected_text}"')

            if params.get('on_success_action') == 'click_center':
                cx = region_rect[0] + region_rect[2] // 2
                cy = region_rect[1] + region_rect[3] // 2
                context.log(f'🖱️ [成功后点击] 坐标: ({cx}, {cy})')
                pyautogui.click(cx, cy)

            return self.build_jump_result(True, params.get('on_success', {}), extra=extra_data)
        else:
            context.log('⏰ [OCR 识别超时] 未能解析出有效文本', 'warning', image=debug_b64)
            return self.build_jump_result(False, params.get('on_failure', {}), extra=extra_data, error='timeout')
