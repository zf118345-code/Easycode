# core/node_executors/base/ocr_recognition.py
import base64
import os
import threading
import time

import cv2
import numpy as np
from core.services.input_dispatcher import click_workspace
from core.services.runtime_target import capture_workspace_region, workspace_rect
from core.vision.frame_cache import prepared_frame

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

_OCR_ENGINE = None
_ENGINE_TYPE = None
_OCR_INIT_LOCK = threading.Lock()
_OCR_INFERENCE_LOCK = threading.Lock()
_OCR_PROCESS_SEMAPHORE = None  # injected by the Player process supervisor

# ⚡ #2 OCR 引擎升级：RapidOCR（PP-OCRv4，界面/游戏文本准确率高）优先，
# ddddocr（轻量验证码向）兜底；可用环境变量 EASYCODE_OCR_ENGINE 强制指定
# （rapidocr / ddddocr / none），部署不再静默失效（失败会打 error 日志）


def _init_rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        # 预热一次（首次推理加载模型较慢，避免节点执行时卡顿）
        import numpy as np

        engine(np.zeros((32, 128, 3), dtype=np.uint8))
        return engine
    except Exception as e:
        print(f' [OCR 引擎] RapidOCR 初始化失败（将回退 ddddocr）: {e}')
        return None


def _init_ddddocr():
    try:
        import ddddocr

        return ddddocr.DdddOcr(show_ad=False)
    except Exception as e:
        print(f' [OCR 引擎初始化失败] ddddocr 导入异常: {e}')
        return None


def get_ocr_engine():
    """返回 (engine_type, engine)。engine_type: 'rapidocr' | 'ddddocr' | 'none'"""
    global _OCR_ENGINE, _ENGINE_TYPE
    if _ENGINE_TYPE is not None:
        return _ENGINE_TYPE, _OCR_ENGINE

    with _OCR_INIT_LOCK:
        if _ENGINE_TYPE is not None:
            return _ENGINE_TYPE, _OCR_ENGINE

        forced = (os.environ.get('EASYCODE_OCR_ENGINE') or '').strip().lower()
        if forced in ('rapidocr', 'ddddocr', 'none'):
            _ENGINE_TYPE = forced
            if forced == 'rapidocr':
                _OCR_ENGINE = _init_rapidocr()
                if _OCR_ENGINE is None:
                    _ENGINE_TYPE = 'none'
            elif forced == 'ddddocr':
                _OCR_ENGINE = _init_ddddocr()
                if _OCR_ENGINE is None:
                    _ENGINE_TYPE = 'none'
            if _ENGINE_TYPE != 'none':
                print(f' [OCR 引擎初始化] {_ENGINE_TYPE} 启动成功（强制指定）')
            return _ENGINE_TYPE, _OCR_ENGINE

        # 默认链：RapidOCR → ddddocr
        _OCR_ENGINE = _init_rapidocr()
        if _OCR_ENGINE is not None:
            _ENGINE_TYPE = 'rapidocr'
            print(' [OCR 引擎初始化] RapidOCR (PP-OCRv4) 启动成功')
        else:
            _OCR_ENGINE = _init_ddddocr()
            _ENGINE_TYPE = 'ddddocr' if _OCR_ENGINE is not None else 'none'
            if _ENGINE_TYPE == 'ddddocr':
                print(' [OCR 引擎初始化] ddddocr 启动成功（RapidOCR 不可用回退）')
            else:
                print(' [OCR 引擎] 无可用 OCR 引擎（rapidocr/ddddocr 均未安装），OCR 节点将超时失败')
        return _ENGINE_TYPE, _OCR_ENGINE


def ocr_engine_recognize(image_bgr) -> str:
    """统一识别入口：按引擎类型调用，返回识别文本"""
    engine_type, engine = get_ocr_engine()
    if engine is None:
        return ''
    try:
        # The bundled OCR engines are stateful native runtimes. A bounded lock
        # prevents concurrent executor threads from corrupting one shared engine
        # or multiplying CPU usage unpredictably. Worker isolation can later
        # replace this with a small inference pool without changing callers.
        process_slot = _OCR_PROCESS_SEMAPHORE
        if process_slot is not None:
            process_slot.acquire()
        try:
            with _OCR_INFERENCE_LOCK:
                if engine_type == 'rapidocr':
                    result, _ = engine(image_bgr)
                    if not result:
                        return ''
                    return ''.join(item[1] for item in result)
                if engine_type == 'ddddocr':
                    _, img_bytes = cv2.imencode('.png', image_bgr)
                    return str(engine.classification(img_bytes.tobytes()) or '')
        finally:
            if process_slot is not None:
                process_slot.release()
    except Exception as e:
        print(f' [OCR 引擎] 识别调用失败: {e}')
        return ''
    return ''


def preprocess_ocr_image(image_bgr, gray_scale: bool = True, gray_threshold: int = 127):
    """Apply the exact same OCR preprocessing for nodes, conditions and previews."""
    if gray_scale:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, int(gray_threshold), 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
    return image_bgr


def recognize_ocr_region(
    context,
    *,
    region_type: str = 'fullwindow',
    region_value=None,
    region_reference_size=None,
    gray_scale: bool = True,
    gray_threshold: int = 127,
    prefer_shared_frame: bool = True,
):
    """Recognize one workspace region and reuse results from the shared step frame.

    Page-state and condition evaluation share ``context._step_screen``.  Caching by
    that frame identity prevents the same region from running OCR repeatedly while
    the engine evaluates several conditions against one captured frame.
    """
    use_region = (
        str(region_type or 'fullwindow').lower() in {'recorded', 'custom'}
        and isinstance(region_value, (list, tuple))
        and len(region_value) == 4
        and float(region_value[2] or 0) > 0
        and float(region_value[3] or 0) > 0
    )
    requested_region = list(region_value) if use_region else None
    shared_screen = getattr(context, '_step_screen', None) if prefer_shared_frame else None

    if shared_screen is not None:
        width, height = shared_screen.size
        if requested_region is None:
            actual_region = (0, 0, width, height)
            screenshot = shared_screen
        else:
            actual_region = workspace_rect(
                context,
                requested_region,
                region_reference_size,
                current_work_area=(0, 0, width, height),
            )
            x, y, region_width, region_height = actual_region
            screenshot = shared_screen.crop((x, y, x + region_width, y + region_height))
        frame_token = id(shared_screen)
    else:
        screenshot, actual_region = capture_workspace_region(
            context,
            requested_region,
            region_reference_size,
        )
        frame_token = None

    cache_key = (
        tuple(actual_region),
        bool(gray_scale),
        int(gray_threshold),
    )
    cache = getattr(context, '_ocr_frame_cache', None)
    if frame_token is not None:
        if not isinstance(cache, dict) or cache.get('frame_token') != frame_token:
            cache = {'frame_token': frame_token, 'results': {}}
            setattr(context, '_ocr_frame_cache', cache)
        cached = cache['results'].get(cache_key)
        if cached is not None:
            return cached

    if shared_screen is not None:
        full_bgr = prepared_frame(context, shared_screen)['bgr']
        if requested_region is None:
            frame_bgr = full_bgr
        else:
            x, y, region_width, region_height = actual_region
            frame_bgr = full_bgr[y:y + region_height, x:x + region_width]
    else:
        frame_bgr = prepared_frame(context, screenshot)['bgr']
    processed_img = preprocess_ocr_image(frame_bgr, gray_scale, gray_threshold)
    engine_type, _ = get_ocr_engine()
    detected_text = ocr_engine_recognize(processed_img).strip()
    result = {
        'text': detected_text,
        'engine': engine_type,
        'region': tuple(int(value) for value in actual_region),
        'processed_image': processed_img,
    }
    if frame_token is not None:
        cache['results'][cache_key] = result
    return result


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

        engine_type, _ = get_ocr_engine()  # ⚡ 引擎初始化（统一识别入口内部调用）

        # ----------------  1. 计算识别区域坐标 ----------------
        if (
            region_type in ('recorded', 'custom')
            and len(region_value) == 4
            and region_value[2] > 0
            and region_value[3] > 0
        ):
            region_rect = region_value
        else:
            region_rect = None

        context.log(f' [OCR 识别定位] 模式: {region_type} | 工作区相对区域: {region_rect or "整个工作区"}')

        # ---------------- 📸 2. 落盘调试准备 ----------------
        debug_dir = os.path.join(context.project_dir, 'debug_screenshots')
        os.makedirs(debug_dir, exist_ok=True)

        start_time = time.time()
        detected_text = ''
        found = False
        debug_b64 = None
        attempt_count = 0

        # ----------------  3. 主识别循环 ----------------
        while time.time() - start_time < timeout:
            attempt_count += 1
            try:
                recognized = recognize_ocr_region(
                    context,
                    region_type=region_type,
                    region_value=region_rect,
                    region_reference_size=params.get('region_reference_size'),
                    gray_scale=gray_scale,
                    gray_threshold=gray_threshold,
                    prefer_shared_frame=False,
                )
                detected_text = recognized['text']
                engine_type = recognized['engine']
                current_region = recognized['region']
                processed_img = recognized['processed_image']

                # ⚡ #13 终局才编码调试图（循环内不再重复 PNG 编码 + base64）
                if debug_b64 is None:
                    debug_b64 = image_to_base64(processed_img)

                if detected_text:
                    found = True
                    break

            except Exception as e:
                context.log(f' [OCR 第 {attempt_count} 次尝试异常]: {e}', 'error')
                break

            time.sleep(context.get_setting('ocr_poll_ms', 300) / 1000.0)

        # ----------------  4. 终局结果处理 ----------------
        extra_data = {'text': detected_text, 'engine': engine_type}
        if debug_b64:
            extra_data['debug_image'] = debug_b64

        if found:
            context.last_ocr_text = detected_text
            context.log(f'[OCR] 识别文字="{detected_text}"', image=debug_b64)

            if save_to_var:
                context.variables[save_to_var] = detected_text
                context.log(f' [变量写入] context.variables[\'{save_to_var}\'] = "{detected_text}"')

            if params.get('on_success_action') == 'click_center':
                cx = current_region[0] + current_region[2] // 2
                cy = current_region[1] + current_region[3] // 2
                result = click_workspace(context, cx, cy, requested_mode='background')
                context.log(
                    f' [OCR成功后点击] 工作区坐标({cx}, {cy}) [{result.get("method", "none")}] '
                    f'| {result.get("message", "")}'
                )
                if not result.get('ok'):
                    return self.build_result(
                        False,
                        error=result.get('message', 'click failed'),
                        extra={**extra_data, 'input': result},
                    )
                extra_data['input'] = result

            return self.build_result(True, extra=extra_data)
        else:
            context.last_ocr_text = ''
            context.log(f'[OCR] 未识别到有效文字 | 区域={list(region_rect) if region_rect else "整个工作区"}', 'warning', image=debug_b64)
        return self.build_result(False, extra=extra_data, error='timeout')
