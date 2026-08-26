"""OCR 节点与页面/条件识别必须共享同一套引擎、区域、运算符和文字日志。"""

from types import SimpleNamespace

import numpy as np
from PIL import Image

from core.conditions.handlers.text_contains import TextContainsEvaluator
from core.node_executors.base.ocr_recognition import OcrRecognitionNodeExecutor


class FakeOcrContext:
    def __init__(self, screen=None, project_dir='.'):
        self._step_screen = screen
        self.variables = {}
        self.last_ocr_text = ''
        self.project_dir = str(project_dir)
        self.logs = []

    def log(self, message, *args, **kwargs):
        self.logs.append(str(message))

    def get_setting(self, _name, default=None):
        return default


def test_text_condition_uses_recorded_region_equals_alias_and_frame_cache(monkeypatch):
    """RapidOCR/其他引擎均走统一入口；同帧同区域只识别一次。"""
    import core.node_executors.base.ocr_recognition as ocr_module

    recognized_shapes = []
    monkeypatch.setattr(ocr_module, 'get_ocr_engine', lambda: ('rapidocr', object()))
    monkeypatch.setattr(
        ocr_module,
        'ocr_engine_recognize',
        lambda image: recognized_shapes.append(image.shape) or '累计登录福利',
    )
    context = FakeOcrContext(Image.new('RGB', (100, 80), 'white'))
    params = {
        'target_text': '累计登录福利',
        'operator': 'equals',
        'region_type': 'recorded',
        'region_value': [10, 20, 30, 18],
        'region_reference_size': [100, 80],
        'gray_scale': False,
    }

    assert TextContainsEvaluator.evaluate(params, context) is True
    assert TextContainsEvaluator.evaluate(params, context) is True

    assert recognized_shapes == [(18, 30, 3)]
    assert context.last_ocr_text == '累计登录福利'
    assert any('[OCR] 识别文字="累计登录福利"' in line for line in context.logs)
    assert any('目标条件=完全等于"累计登录福利" | 结果=命中' in line for line in context.logs)
    assert all('置信度' not in line for line in context.logs)


def test_text_condition_empty_result_reports_region_not_confidence(monkeypatch):
    import core.node_executors.base.ocr_recognition as ocr_module

    monkeypatch.setattr(ocr_module, 'get_ocr_engine', lambda: ('ddddocr', object()))
    monkeypatch.setattr(ocr_module, 'ocr_engine_recognize', lambda _image: '')
    context = FakeOcrContext(Image.new('RGB', (80, 60), 'white'))

    assert TextContainsEvaluator.evaluate({
        'target_text': '确认',
        'exist_mode': 'contains',
        'region_type': 'recorded',
        'region_value': [5, 6, 20, 10],
        'region_reference_size': [80, 60],
    }, context) is False

    assert any('未识别到有效文字 | 区域=[5, 6, 20, 10]' in line for line in context.logs)
    assert all('置信度' not in line for line in context.logs)


def test_standalone_ocr_node_logs_text_for_any_engine(monkeypatch, tmp_path):
    import core.node_executors.base.ocr_recognition as ocr_module

    monkeypatch.setattr(ocr_module, 'get_ocr_engine', lambda: ('rapidocr', object()))
    monkeypatch.setattr(ocr_module, 'image_to_base64', lambda _image: None)
    monkeypatch.setattr(ocr_module, 'recognize_ocr_region', lambda *_args, **_kwargs: {
        'text': '立即购买',
        'engine': 'rapidocr',
        'region': (20, 30, 60, 24),
        'processed_image': np.zeros((24, 60, 3), dtype=np.uint8),
    })
    context = FakeOcrContext(project_dir=tmp_path)
    node = SimpleNamespace(params={
        'region_type': 'recorded',
        'region_value': [20, 30, 60, 24],
        'timeout': 100,
        'gray_scale': False,
        'on_success_action': 'none',
    })

    result = OcrRecognitionNodeExecutor().execute(node, context)

    assert result['success'] is True
    assert result['text'] == '立即购买'
    assert context.last_ocr_text == '立即购买'
    assert any('[OCR] 识别文字="立即购买"' in line for line in context.logs)
    assert all('置信度' not in line for line in context.logs)
