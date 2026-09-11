from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest

from core.vnext import vision_preview_v6


def _preview_shape(data_url: str) -> tuple[int, int]:
    encoded = data_url.split(',', 1)[1]
    image = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return tuple(int(item) for item in image.shape[:2])


class _PreviewDriver:
    frame_is_bgr = True

    def __init__(self, *, ocr: bool = False, image_match: bool = True, image_similarity: float = 0.93):
        self.ocr = ocr
        self.image_match = image_match
        self.image_similarity = image_similarity
        self.closed = False
        self.calls: list[tuple[str, dict]] = []
        self._frame_references: dict[str, dict] = {}

    def execute(self, opcode, arguments, _cancelled):
        self.calls.append((opcode, arguments))
        if opcode == 'target.capture_frame':
            self._frame_references['frame.1'] = {
                'pixels': np.full((40, 80, 3), 235, dtype=np.uint8),
            }
            return {
                'kind': 'frame_ref',
                'frame_ref.field.frame_id': 'frame.1',
                'frame_ref.field.captured_at': '2026-09-06T12:00:00Z',
            }
        if opcode == 'vision.find':
            if not self.image_match:
                return None
            return {
                'image_match.field.region': {'x': 4, 'y': 5, 'width': 12, 'height': 8},
                'image_match.field.similarity': self.image_similarity,
            }
        if opcode == 'text.recognize':
            return {
                'ocr_result.field.text': '当前体力 86',
                'ocr_result.field.lines': [{'text': '当前体力 86'}],
                'ocr_result.field.region': {'x': 2, 'y': 3, 'width': 30, 'height': 12},
            }
        raise AssertionError(opcode)

    def _crop(self, frame, region):
        x, y, width, height = region
        return frame[y:y + height, x:x + width], x, y

    @staticmethod
    def _v6_ocr_preprocess(value):
        return (
            bool(value.get('ocr_preprocess.field.grayscale', False)),
            bool(value.get('ocr_preprocess.field.binary', False)),
            int(value.get('ocr_preprocess.field.threshold', 127)),
            bool(value.get('ocr_preprocess.field.invert', False)),
        )

    def image_match_diagnostic(self):
        return {'best_similarity': self.image_similarity, 'threshold': 0.9}

    def close(self):
        self.closed = True


@pytest.mark.parametrize('function_id', (
    'official.image.click_once',
    'official.image.click_position_until_visible',
    'official.image.click_position_until_hidden',
))
def test_image_preview_captures_once_and_never_executes_the_click_or_wait_opcode(monkeypatch, function_id):
    driver = _PreviewDriver()
    monkeypatch.setattr(vision_preview_v6, 'create_target_driver', lambda *_args: driver)

    result = vision_preview_v6.preview_vision(
        'D:/project',
        {'target_id': 'target.windows'},
        function_id=function_id,
        image_asset_id='asset.button',
        similarity=0.9,
        region=[1, 2, 30, 20],
    )

    assert [opcode for opcode, _ in driver.calls] == ['target.capture_frame', 'vision.find']
    find_arguments = driver.calls[1][1]
    assert find_arguments['official.image.find.parameter.frame']['frame_ref.field.frame_id'] == 'frame.1'
    assert find_arguments['official.image.find.parameter.image']['asset_id'] == 'asset.button'
    assert result['kind'] == 'image'
    assert result['matched'] is True
    assert result['similarity'] == 0.93
    assert result['preview_data_url'].startswith('data:image/png;base64,')
    assert _preview_shape(result['preview_data_url']) == (20, 30)
    assert result['requested_region'] == [1, 2, 30, 20]
    assert result['actual_region'] == [1, 2, 30, 20]
    assert result['region_clipped'] is False
    assert result['region_empty'] is False
    assert driver.closed is True


def test_image_preview_preserves_the_best_score_below_threshold(monkeypatch):
    driver = _PreviewDriver(image_match=False, image_similarity=0.842)
    monkeypatch.setattr(vision_preview_v6, 'create_target_driver', lambda *_args: driver)

    result = vision_preview_v6.preview_vision(
        'D:/project',
        {'target_id': 'target.windows'},
        function_id='official.image.find',
        image_asset_id='asset.button',
        similarity=0.85,
    )

    assert result['matched'] is False
    assert result['similarity'] == 0.842
    assert result['threshold'] == 0.85


def test_image_preview_returns_only_the_clipped_analysis_pixels(monkeypatch):
    driver = _PreviewDriver(image_match=False, image_similarity=0.42)
    monkeypatch.setattr(vision_preview_v6, 'create_target_driver', lambda *_args: driver)

    result = vision_preview_v6.preview_vision(
        'D:/project',
        {'target_id': 'target.windows'},
        function_id='official.image.find',
        image_asset_id='asset.button',
        similarity=0.85,
        region=[70, 30, 20, 20],
    )

    assert _preview_shape(result['preview_data_url']) == (10, 10)
    assert result['requested_region'] == [70, 30, 20, 20]
    assert result['actual_region'] == [70, 30, 10, 10]
    assert result['region_clipped'] is True
    assert result['region_empty'] is False


def test_ocr_preview_returns_the_processed_crop_and_current_match_result(monkeypatch):
    driver = _PreviewDriver(ocr=True)
    monkeypatch.setattr(vision_preview_v6, 'create_target_driver', lambda *_args: driver)

    result = vision_preview_v6.preview_vision(
        'D:/project',
        {'target_id': 'target.adb'},
        function_id='official.text.match',
        region=[2, 3, 30, 12],
        preprocess={
            'ocr_preprocess.field.grayscale': True,
            'ocr_preprocess.field.binary': True,
            'ocr_preprocess.field.threshold': 145,
            'ocr_preprocess.field.invert': False,
        },
        expected_text='体力',
        match_mode='contains',
    )

    assert [opcode for opcode, _ in driver.calls] == ['target.capture_frame', 'text.recognize']
    ocr_arguments = driver.calls[1][1]
    assert ocr_arguments['official.text.recognize.parameter.frame']['frame_ref.field.frame_id'] == 'frame.1'
    assert result['kind'] == 'ocr'
    assert result['matched'] is True
    assert result['text'] == '当前体力 86'
    assert result['line_count'] == 1
    assert result['threshold'] == 145
    assert result['preview_data_url'].startswith('data:image/png;base64,')
    assert _preview_shape(result['preview_data_url']) == (12, 30)
    assert result['actual_region'] == [2, 3, 30, 12]
    assert driver.closed is True


def test_ocr_preview_keeps_a_useful_frame_when_region_has_no_intersection(monkeypatch):
    class OutsideRegionDriver(_PreviewDriver):
        def execute(self, opcode, arguments, cancelled):
            if opcode != 'text.recognize':
                return super().execute(opcode, arguments, cancelled)
            self.calls.append((opcode, arguments))
            return {
                'ocr_result.field.text': '',
                'ocr_result.field.lines': [],
                'ocr_result.field.region': {'x': 80, 'y': 40, 'width': 0, 'height': 0},
            }

    driver = OutsideRegionDriver(ocr=True)
    monkeypatch.setattr(vision_preview_v6, 'create_target_driver', lambda *_args: driver)

    result = vision_preview_v6.preview_vision(
        'D:/project',
        {'target_id': 'target.adb'},
        function_id='official.text.recognize',
        region=[90, 70, 20, 20],
    )

    assert result['kind'] == 'ocr'
    assert result['text'] == ''
    assert result['line_count'] == 0
    assert result['preview_data_url'] == ''
    assert result['actual_region'] == [80, 40, 0, 0]
    assert result['region_clipped'] is True
    assert result['region_empty'] is True
    assert driver.closed is True
