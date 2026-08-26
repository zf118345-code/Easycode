import cv2
import numpy as np
from PIL import Image


def test_prepared_template_match_preserves_legacy_result():
    from core.utils import match_prepared_template_cv, match_template_cv, prepare_template_cv

    random = np.random.default_rng(20260824)
    template_bgr = random.integers(0, 256, size=(12, 16, 3), dtype=np.uint8)
    screen_rgb = np.zeros((80, 120, 3), dtype=np.uint8)
    screen_rgb[30:42, 45:61] = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2RGB)

    legacy_confidence, legacy_center = match_template_cv(
        screen_rgb,
        template_bgr,
        scales=(1.0,),
    )
    prepared = prepare_template_cv(template_bgr, scales=(1.0,))
    prepared_confidence, prepared_center = match_prepared_template_cv(screen_rgb, prepared)

    assert prepared_center == legacy_center == (53, 36)
    assert prepared_confidence == legacy_confidence
    assert prepared_confidence > 0.99


def test_prepared_template_deduplicates_equivalent_scale_sizes():
    from core.utils import prepare_template_cv

    template = np.zeros((10, 10, 3), dtype=np.uint8)
    variants = prepare_template_cv(template, scales=(1.0, 1.0, 0.99))
    assert [(width, height) for width, height, _ in variants] == [(10, 10)]


def test_region_capture_reads_window_geometry_only_once(monkeypatch):
    from types import SimpleNamespace
    from core.services import runtime_target

    calls = {'refresh': 0}

    def refresh(_context):
        calls['refresh'] += 1
        return 10, 20, 960, 540

    monkeypatch.setattr(runtime_target, 'refresh_work_area', refresh)
    monkeypatch.setattr(
        runtime_target.screenshot_service,
        'capture',
        lambda **_kwargs: Image.new('RGB', (100, 80)),
    )
    context = SimpleNamespace(window_hwnd=None, is_emulator=False)
    image, relative = runtime_target.capture_workspace_region(
        context,
        rect=[10, 20, 100, 80],
        reference_size=[960, 540],
    )
    assert calls['refresh'] == 1
    assert relative == (10, 20, 100, 80)
    assert image.size == (100, 80)


def test_binary_template_preview_does_not_capture_minimized_workspace(monkeypatch):
    import core.services.vision_service as vision_module
    from core.services.vision_service import AssetService, VisionService

    template = np.zeros((16, 20, 3), dtype=np.uint8)
    template[:, 10:] = 255
    monkeypatch.setattr(
        AssetService,
        'resolve',
        lambda *_args, **_kwargs: {'full_path': 'virtual-template.png'},
    )
    monkeypatch.setattr(vision_module, 'load_image', lambda *_args, **_kwargs: template.copy())
    monkeypatch.setattr(
        VisionService,
        '_capture_project_workspace',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('预览不应读取工作窗口')),
    )

    result = VisionService.test_image(
        'virtual-project',
        'asset://template',
        True,
        127,
        preview_only=True,
    )
    assert result['status'] == 'success'
    assert result['image'].startswith('data:image/png;base64,')
    assert result['confidence'] is None


def test_window_capture_rejects_minimized_target_before_cached_wgc(monkeypatch):
    import sys
    import types
    from core.services import screenshot_service

    win32gui = types.ModuleType('win32gui')
    win32gui.IsWindow = lambda _hwnd: True
    win32gui.IsIconic = lambda _hwnd: True
    monkeypatch.setitem(sys.modules, 'win32gui', win32gui)
    monkeypatch.setattr(
        screenshot_service,
        '_capture_window_printwindow',
        lambda _hwnd: (_ for _ in ()).throw(AssertionError('最小化窗口不应继续捕获')),
    )

    image, info = screenshot_service.capture_window_with_info(123)

    assert image is None
    assert info['capability'] == 'foreground_required'
    assert '最小化' in info['message']
