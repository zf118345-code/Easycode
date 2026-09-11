# tests/test_region_coords.py
# ⚡ 回归：capture(region) 契约 (left, top, right, bottom)——
# image_recognition / ocr_recognition 此前传 (x, y, w, h) 导致截图区域错误（智能跳转/识别匹配不到的主因之一）
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image


class FakeContext:
    def __init__(self, window_rect=(100, 50, 800, 600)):
        self._rect = window_rect
        self.logs = []
        self.project_dir = 'D:/test'
        self.variables = {}
        self._memory_templates = {'tpl': np.zeros((10, 10, 3), dtype=np.uint8)}
        self.image_log_enabled = False
        self.text_log_enabled = False

    def get_window_rect(self):
        return self._rect

    def is_window_mode(self):
        return True

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)

    def get_setting(self, key, default=None):
        return default


def _make_screen(w=1920, h=1080):
    return Image.fromarray(np.full((h, w, 3), 200, dtype=np.uint8))


def test_image_recognition_region_converts_to_ltrb(monkeypatch):
    """recorded 区域 (x,y,w,h) → capture 收到 (x, y, x+w, y+h)；窗口偏移叠加正确"""
    from core.node_executors.base import image_recognition
    from core.services import screenshot_service

    captured = {}

    def fake_capture(region=None):
        captured['region'] = region
        return _make_screen()

    monkeypatch.setattr(screenshot_service, 'capture', fake_capture)
    monkeypatch.setattr(image_recognition, 'match_template_cv', lambda *a, **k: (0.0, None))
    monkeypatch.setattr(image_recognition, 'load_image', lambda *a, **k: np.zeros((10, 10, 3), dtype=np.uint8))

    executor = image_recognition.ImageRecognitionNodeExecutor()
    ctx = FakeContext(window_rect=(146, 114, 1280, 720))  # 模拟器工作区
    node = type('N', (), {
        'node_id': 'n1', 'node_name': '识别', 'node_type': 'image_recognition',
        'params': {
            'image_source': 'tpl', 'region_type': 'recorded', 'region_value': [10, 20, 100, 80],
            'region_is_relative': True, 'threshold': 85, 'timeout': 100, 'gray_scale': False,
            'execution_mode': 'wait_present',
        },
    })()
    # 执行一次循环即退出（timeout 很小，匹配永不命中）
    executor.execute(node, ctx)
    assert captured['region'] == (156, 134, 256, 214), captured['region']


def test_image_recognition_fullwindow_uses_ltrb(monkeypatch):
    """fullwindow 模式：window_rect (l,t,w,h) → capture 收到 (l, t, l+w, t+h)"""
    from core.node_executors.base import image_recognition
    from core.services import screenshot_service

    captured = {}

    def fake_capture(region=None):
        captured['region'] = region
        return _make_screen()

    monkeypatch.setattr(screenshot_service, 'capture', fake_capture)
    monkeypatch.setattr(image_recognition, 'match_template_cv', lambda *a, **k: (0.0, None))
    monkeypatch.setattr(image_recognition, 'load_image', lambda *a, **k: np.zeros((10, 10, 3), dtype=np.uint8))

    executor = image_recognition.ImageRecognitionNodeExecutor()
    ctx = FakeContext(window_rect=(146, 114, 1280, 720))
    node = type('N', (), {
        'node_id': 'n2', 'node_name': '识别', 'node_type': 'image_recognition',
        'params': {'image_source': 'tpl', 'region_type': 'fullwindow', 'threshold': 85, 'timeout': 100, 'execution_mode': 'wait_present'},
    })()
    executor.execute(node, ctx)
    assert captured['region'] == (146, 114, 1426, 834), captured['region']


def test_ocr_recognition_region_converts_to_ltrb(monkeypatch):
    """OCR 区域同样转 (x, y, x+w, y+h)"""
    from core.node_executors.base import ocr_recognition
    from core.services import screenshot_service

    captured = {}

    def fake_capture(region=None):
        captured['region'] = region
        return _make_screen()

    monkeypatch.setattr(screenshot_service, 'capture', fake_capture)
    monkeypatch.setattr(ocr_recognition, 'ocr_engine_recognize', lambda img: '')

    executor = ocr_recognition.OcrRecognitionNodeExecutor()
    ctx = FakeContext(window_rect=(146, 114, 1280, 720))
    node = type('N', (), {
        'node_id': 'n3', 'node_name': 'OCR', 'node_type': 'ocr_recognition',
        'params': {'region_type': 'recorded', 'region_value': [5, 6, 30, 40], 'timeout': 100, 'gray_scale': False},
    })()
    executor.execute(node, ctx)
    assert captured['region'] == (151, 120, 181, 160), captured['region']


def test_image_exists_captures_workspace_rect(monkeypatch):
    """页面特征 image_exists：截工作区图（window_rect），与模板录制坐标系一致"""
    from core.conditions.handlers.image_exists import ImageExistsEvaluator
    from core.services import screenshot_service

    captured = {}

    def fake_capture(region=None):
        captured['region'] = region
        return _make_screen()

    monkeypatch.setattr(screenshot_service, 'capture', fake_capture)
    from core.vision.memory_matcher import MemoryTemplateMatcher
    monkeypatch.setattr(MemoryTemplateMatcher, 'match_in_memory', classmethod(lambda cls, **kw: (0.99, (5, 5))))

    ctx = FakeContext(window_rect=(146, 114, 1280, 720))
    params = {
        'image_source': 'tpl.png', 'threshold': 0.8,
        'region_type': 'recorded', 'region_value': [10, 20, 100, 80],
    }
    assert ImageExistsEvaluator.evaluate(params, ctx) is True
    # 必须截工作区（l, t, l+w, t+h），而非全屏
    assert captured['region'] == (146, 114, 1426, 834), captured['region']


def test_page_state_logs_chinese_names():
    """页面状态日志：显示节点名（回退链 page_name → node_name → page_id），非裸 id"""
    from core.node_executors.base.page_state import PageStateNodeExecutor

    node = type('N', (), {
        'node_id': 'n_x', 'node_name': '主城', 'node_type': 'page_state',
            'params': {'page_id': 'page_x', 'features': [{'condition_type': 'image_exists', 'image_source': 'tpl'}]},
    })()
    ctx = FakeContext()
    # 特征评估会走 image_exists → mock 掉 screenshot 路径
    ctx.get_window_rect = lambda: (0, 0, 1920, 1080)

    # 直接测 execute 的日志输出（patch evaluate_condition 返回 False）
    from core.conditions import evaluator
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(evaluator, 'evaluate_condition', lambda cond, context: False)
    executor = PageStateNodeExecutor()
    executor.execute(node, ctx)
    monkeypatch.undo()

    joined = '\n'.join(ctx.logs)
    assert '[页面状态] 评估页面: [主城]' in joined, joined
    assert '主城' in joined
    assert '图像存在' in joined  # 条件类型中文化


def test_minimized_emulator_uses_configured_workspace_size(monkeypatch):
    """ADB 模拟器最小化后仍使用项目工作区，不读取 -32000 窗口坐标。"""
    import win32gui
    from core.services.runtime_target import refresh_work_area

    ctx = SimpleNamespace(
        is_emulator=True,
        window_hwnd=123,
        window_rect=(-32000, -32000, 1, 1),
        variables={
            'target_content_size': [960, 540],
            'window_content_offset': {'top': 40, 'bottom': 0, 'left': 0, 'right': 0},
        },
    )
    monkeypatch.setattr(win32gui, 'IsWindow', lambda hwnd: True)
    monkeypatch.setattr(win32gui, 'IsIconic', lambda hwnd: True)

    assert refresh_work_area(ctx) == (0, 0, 960, 540)
    assert ctx.variables['window_rect'] == (0, 0, 960, 540)
