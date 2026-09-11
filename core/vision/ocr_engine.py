"""Runtime-neutral OCR engine and image preprocessing boundary.

This module intentionally has no dependency on legacy node executors,
conditions, IDE services, or project models.  Frozen vNext Players can import
and execute it without running an executor package ``__init__``.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import cv2


_OCR_ENGINE: Any = None
_ENGINE_TYPE: str | None = None
_OCR_INIT_LOCK = threading.Lock()
_OCR_INFERENCE_LOCK = threading.Lock()
_OCR_PROCESS_SEMAPHORE: Any = None


class OcrAdapterError(RuntimeError):
    """The OCR adapter could not run; an empty recognition is not an error."""

    def __init__(self, message: str, *, reason: str = 'inference_failed') -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class OcrAdapterLine:
    text: str
    region: tuple[int, int, int, int]


@dataclass(frozen=True)
class OcrAdapterResult:
    engine_type: str
    text: str
    lines: tuple[OcrAdapterLine, ...]


def _init_rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np

        engine = RapidOCR()
        engine(np.zeros((32, 128, 3), dtype=np.uint8))
        return engine
    except Exception as exc:
        print(f' [OCR 引擎] RapidOCR 初始化失败（将回退 ddddocr）: {exc}')
        return None


def _init_ddddocr():
    try:
        import ddddocr

        return ddddocr.DdddOcr(show_ad=False)
    except Exception as exc:
        print(f' [OCR 引擎初始化失败] ddddocr 导入异常: {exc}')
        return None


def get_ocr_engine():
    """Return ``(engine_type, engine)`` with one process-local lazy engine."""

    global _OCR_ENGINE, _ENGINE_TYPE
    if _ENGINE_TYPE is not None:
        return _ENGINE_TYPE, _OCR_ENGINE
    with _OCR_INIT_LOCK:
        if _ENGINE_TYPE is not None:
            return _ENGINE_TYPE, _OCR_ENGINE
        forced = (os.environ.get('EASYCODE_OCR_ENGINE') or '').strip().lower()
        if forced in {'rapidocr', 'ddddocr', 'none'}:
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
                print(' [OCR 引擎] 无可用 OCR 引擎（rapidocr/ddddocr 均未安装）')
        return _ENGINE_TYPE, _OCR_ENGINE


def ocr_engine_recognize_detailed(image_bgr) -> OcrAdapterResult:
    """Run RapidOCR/ddddocr behind one structured, non-silent adapter."""

    engine_type, engine = get_ocr_engine()
    if engine is None:
        raise OcrAdapterError(
            '没有可用的 OCR 引擎，请安装 RapidOCR 或 ddddocr',
            reason='engine_unavailable',
        )
    process_slot = _OCR_PROCESS_SEMAPHORE
    try:
        if process_slot is not None:
            process_slot.acquire()
        try:
            with _OCR_INFERENCE_LOCK:
                if engine_type == 'rapidocr':
                    result, _ = engine(image_bgr)
                    if not result:
                        return OcrAdapterResult(engine_type='rapidocr', text='', lines=())
                    lines = []
                    for item in result:
                        if not isinstance(item, (list, tuple)) or len(item) < 2:
                            continue
                        text = str(item[1] or '').strip()
                        if not text:
                            continue
                        points = item[0]
                        try:
                            xs = [float(point[0]) for point in points]
                            ys = [float(point[1]) for point in points]
                            left, top = int(min(xs)), int(min(ys))
                            right, bottom = int(max(xs)), int(max(ys))
                            region = (left, top, max(1, right - left), max(1, bottom - top))
                        except (TypeError, ValueError, IndexError):
                            height, width = image_bgr.shape[:2]
                            region = (0, 0, int(width), int(height))
                        lines.append(OcrAdapterLine(text=text, region=region))
                    return OcrAdapterResult(
                        engine_type='rapidocr',
                        text='\n'.join(line.text for line in lines),
                        lines=tuple(lines),
                    )
                if engine_type == 'ddddocr':
                    ok, img_bytes = cv2.imencode('.png', image_bgr)
                    if not ok:
                        raise OcrAdapterError('OCR 输入图像编码失败')
                    text = str(engine.classification(img_bytes.tobytes()) or '').strip()
                    height, width = image_bgr.shape[:2]
                    lines = (
                        (OcrAdapterLine(text=text, region=(0, 0, int(width), int(height))),)
                        if text else ()
                    )
                    return OcrAdapterResult(engine_type='ddddocr', text=text, lines=lines)
                raise OcrAdapterError(f'不支持的 OCR 引擎：{engine_type}')
        finally:
            if process_slot is not None:
                process_slot.release()
    except OcrAdapterError:
        raise
    except Exception as exc:
        raise OcrAdapterError(f'OCR 识别调用失败：{exc}') from exc


def ocr_engine_recognize(image_bgr) -> str:
    """Legacy text-only adapter; vNext uses the structured entry point."""

    try:
        return ocr_engine_recognize_detailed(image_bgr).text
    except OcrAdapterError as exc:
        print(f' [OCR 引擎] 识别调用失败: {exc}')
        return ''


def preprocess_ocr_image(
    image_bgr,
    gray_scale: bool = True,
    gray_threshold: int = 127,
    *,
    binary: bool | None = None,
    invert: bool = False,
):
    """Apply the same OCR preprocessing for vNext, legacy nodes and previews."""

    binary = bool(gray_scale) if binary is None else bool(binary)
    if gray_scale or binary:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        if binary:
            _, gray = cv2.threshold(gray, int(gray_threshold), 255, cv2.THRESH_BINARY)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        result = image_bgr
    return cv2.bitwise_not(result) if invert else result


__all__ = [
    'OcrAdapterError',
    'OcrAdapterLine',
    'OcrAdapterResult',
    'get_ocr_engine',
    'ocr_engine_recognize',
    'ocr_engine_recognize_detailed',
    'preprocess_ocr_image',
]
