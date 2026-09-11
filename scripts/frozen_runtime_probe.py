"""Trusted one-shot probe loaded by a frozen Player extension worker.

This is release-verification code, not a public extension.  It forces the
dependencies that normal execution loads lazily so packaging regressions are
found before a user's flow reaches the first OCR, control, input, file,
network, message, or standard operation.
"""

from __future__ import annotations


def run(_context):
    import sys

    import numpy as np

    from core.services import background_input, screenshot_service, uia_service
    from core.vision.ocr_engine import get_ocr_engine, ocr_engine_recognize_detailed
    from core.vnext import (
        extension_runtime_v6,
        file_runtime_v6,
        message_runtime_v6,
        network_runtime_v6,
        platform_runtime_v6,
        standard_functions_v6,
        target_runtime,
    )

    engine_type, engine = get_ocr_engine()
    if engine is None:
        raise RuntimeError('冻结 Player 没有可用 OCR 引擎')
    ocr_result = ocr_engine_recognize_detailed(
        np.full((64, 256, 3), 255, dtype=np.uint8)
    )
    forbidden_roots = (
        'core.node_executors',
        'core.conditions',
        'core.params',
        'core.player',
    )
    forbidden_loaded = sorted(
        name
        for name in sys.modules
        if any(name == root or name.startswith(root + '.') for root in forbidden_roots)
    )
    if forbidden_loaded:
        raise RuntimeError(f'冻结边界加载了旧包：{forbidden_loaded}')
    providers = {
        module.__name__
        for module in (
            background_input,
            screenshot_service,
            uia_service,
            extension_runtime_v6,
            file_runtime_v6,
            message_runtime_v6,
            network_runtime_v6,
            platform_runtime_v6,
            standard_functions_v6,
            target_runtime,
        )
    }
    return {
        'ocr_engine': engine_type,
        'ocr_probe_text': ocr_result.text,
        'providers': sorted(providers),
        'forbidden_loaded': forbidden_loaded,
    }

