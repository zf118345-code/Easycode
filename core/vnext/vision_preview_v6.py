"""Side-effect-free authoring previews for the built-in image and OCR functions."""

from __future__ import annotations

import base64
from typing import Any

from .runtime import RuntimeFailure
from .target_runtime import TargetDriver, create_target_driver
from .vision_analysis_v6 import frame_to_bgr


def _preview_data_url(image: Any, *, max_width: int = 1100, max_height: int = 680) -> str:
    import cv2

    prepared = frame_to_bgr(image, frame_is_bgr=True)
    height, width = (int(value) for value in prepared.shape[:2])
    scale = min(1.0, max_width / max(1, width), max_height / max(1, height))
    if scale < 1.0:
        prepared = cv2.resize(
            prepared,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode('.png', prepared)
    if not ok:
        raise RuntimeFailure('无法生成识别预览图', error_id='vision.preview_encode_failed')
    return 'data:image/png;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii')


def _frame_pixels(driver: Any, reference: dict[str, Any]) -> Any:
    frame_id = str(reference.get('frame_ref.field.frame_id') or '')
    stored = getattr(driver, '_frame_references', {}).get(frame_id)
    if not isinstance(stored, dict) or 'pixels' not in stored:
        raise RuntimeFailure('当前画面已经失效，请重新测试', error_id='vision.frame_reference_expired')
    return stored['pixels']


def _region_tuple(value: Any) -> list[int] | None:
    if value is None:
        return None
    return [int(item) for item in value]


def preview_vision(
    project_path: str,
    target: dict[str, Any],
    *,
    function_id: str,
    region: list[int] | None = None,
    image_asset_id: str = '',
    similarity: float = 0.85,
    language: str = 'auto',
    preprocess: dict[str, Any] | None = None,
    expected_text: str = '',
    match_mode: str = 'contains',
) -> dict[str, Any]:
    """Capture once and exercise the same runtime adapters used by a real call."""

    driver = create_target_driver(project_path, target)
    if driver is None:
        raise RuntimeFailure('当前语句没有可测试的运行目标', error_id='target.missing')
    try:
        frame_reference = driver.execute('target.capture_frame', {}, lambda: False)
        frame = _frame_pixels(driver, frame_reference)
        if function_id.startswith('official.image.'):
            if not image_asset_id:
                raise RuntimeFailure('请先选择图片资源', error_id='vision.asset_reference_invalid')
            arguments = {
                'official.image.find.parameter.image': {
                    'kind': 'asset_ref',
                    'asset_id': image_asset_id,
                },
                'official.image.find.parameter.similarity': similarity,
                'official.image.find.parameter.region': _region_tuple(region),
                'official.image.find.parameter.frame': frame_reference,
            }
            match = driver.execute('vision.find', arguments, lambda: False)
            diagnostic_reader = getattr(driver, 'image_match_diagnostic', None)
            diagnostic = diagnostic_reader() if callable(diagnostic_reader) else {}
            best_similarity = diagnostic.get('best_similarity') if isinstance(diagnostic, dict) else None
            if not isinstance(best_similarity, (int, float)) and match:
                best_similarity = match.get('image_match.field.similarity')
            analysis_crop, _, _, crop_meta = TargetDriver._analysis_crop(frame, _region_tuple(region))
            preview_data_url = ''
            if analysis_crop is not None:
                preview = frame_to_bgr(
                    analysis_crop,
                    frame_is_bgr=bool(getattr(driver, 'frame_is_bgr', False)),
                ).copy()
            else:
                preview = None
            if match and preview is not None:
                import cv2

                rect = match['image_match.field.region']
                actual_x, actual_y = (int(item) for item in crop_meta['actual_region'][:2])
                x, y = int(rect['x']) - actual_x, int(rect['y']) - actual_y
                width, height = int(rect['width']), int(rect['height'])
                cv2.rectangle(preview, (x, y), (x + width, y + height), (74, 171, 255), 2)
            if preview is not None:
                preview_data_url = _preview_data_url(preview)
            return {
                'kind': 'image',
                'preview_data_url': preview_data_url,
                'matched': match is not None,
                'similarity': float(best_similarity) if isinstance(best_similarity, (int, float)) else None,
                'threshold': float(similarity),
                'text': '',
                'line_count': 0,
                'target_id': str(target.get('target_id') or ''),
                'captured_at': frame_reference.get('frame_ref.field.captured_at'),
                'requested_region': crop_meta['requested_region'],
                'actual_region': crop_meta['actual_region'],
                'region_clipped': bool(crop_meta['region_clipped']),
                'region_empty': bool(crop_meta['region_empty']),
            }

        if function_id not in {
            'official.text.recognize', 'official.text.match', 'official.text.wait_visible',
        }:
            raise RuntimeFailure('当前函数不支持无副作用预览', error_id='vision.preview_unsupported')
        arguments = {
            'official.text.recognize.parameter.region': _region_tuple(region),
            'official.text.recognize.parameter.language': language,
            'official.text.recognize.parameter.preprocess': preprocess or {},
            'official.text.recognize.parameter.frame': frame_reference,
        }
        result = driver.execute('text.recognize', arguments, lambda: False)
        actual_region = result['ocr_result.field.region']
        _, _, _, crop_meta = TargetDriver._analysis_crop(frame, _region_tuple(region))
        from core.vision.ocr_engine import preprocess_ocr_image

        grayscale, binary, threshold, invert = driver._v6_ocr_preprocess(preprocess or {})
        if int(actual_region['width']) <= 0 or int(actual_region['height']) <= 0:
            processed = None
        else:
            crop, _, _ = driver._crop(frame, [
                actual_region['x'], actual_region['y'], actual_region['width'], actual_region['height'],
            ])
            processed = preprocess_ocr_image(
                frame_to_bgr(crop, frame_is_bgr=bool(getattr(driver, 'frame_is_bgr', False))),
                gray_scale=grayscale or binary,
                gray_threshold=threshold,
                binary=binary,
                invert=invert,
            )
        text = str(result.get('ocr_result.field.text') or '')
        normalized_mode = {'完全等于': 'exact', '等于': 'exact', '正则': 'regex'}.get(match_mode, match_mode)
        matched = None
        if expected_text:
            import re

            if normalized_mode == 'exact':
                matched = text == expected_text
            elif normalized_mode == 'regex':
                try:
                    matched = re.search(expected_text, text) is not None
                except re.error as exc:
                    raise RuntimeFailure(f'正则表达式无效：{exc}', error_id='text.regex_invalid') from exc
            else:
                matched = expected_text in text
        return {
            'kind': 'ocr',
            'preview_data_url': _preview_data_url(processed) if processed is not None else '',
            'matched': matched,
            'similarity': None,
            'threshold': threshold if binary else None,
            'text': text,
            'line_count': len(result.get('ocr_result.field.lines') or []),
            'target_id': str(target.get('target_id') or ''),
            'captured_at': frame_reference.get('frame_ref.field.captured_at'),
            'requested_region': crop_meta['requested_region'],
            'actual_region': [
                int(actual_region['x']), int(actual_region['y']),
                int(actual_region['width']), int(actual_region['height']),
            ],
            'region_clipped': bool(crop_meta['region_clipped']),
            'region_empty': int(actual_region['width']) <= 0 or int(actual_region['height']) <= 0,
        }
    finally:
        close = getattr(driver, 'close', None)
        if callable(close):
            close()
