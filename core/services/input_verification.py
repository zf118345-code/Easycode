"""Optional semantic verification for delivered input events."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from core.services.runtime_target import capture_workspace


def frame_signature(image, *, width: int = 64, height: int = 36) -> np.ndarray:
    return np.asarray(image.convert('L').resize((width, height)), dtype=np.float32)


def capture_signature(context) -> np.ndarray:
    return frame_signature(capture_workspace(context))


def verify_frame_change(
    context,
    before: np.ndarray,
    *,
    timeout_ms: int = 600,
    poll_ms: int = 30,
    threshold: float = 0.012,
) -> dict[str, Any]:
    """Wait until the workspace differs materially from ``before``.

    This verifies that an input produced a visible effect, not that the target
    reached a particular business state. Image/page nodes should continue to
    use their stronger explicit stop conditions.
    """
    started = time.monotonic()
    deadline = started + max(0, int(timeout_ms or 0)) / 1000.0
    best = 0.0
    samples = 0
    last_error = ''
    while True:
        try:
            current = capture_signature(context)
            samples += 1
            difference = float(np.mean(np.abs(current - before)) / 255.0)
            best = max(best, difference)
            if difference >= max(0.0001, float(threshold or 0.012)):
                return {
                    'verified': True,
                    'strategy': 'frame_change',
                    'difference': round(difference, 5),
                    'samples': samples,
                    'elapsed_ms': round((time.monotonic() - started) * 1000, 2),
                }
        except Exception as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            return {
                'verified': False,
                'strategy': 'frame_change',
                'difference': round(best, 5),
                'samples': samples,
                'elapsed_ms': round((time.monotonic() - started) * 1000, 2),
                'error': last_error,
            }
        time.sleep(max(10, int(poll_ms or 30)) / 1000.0)


def mark_background_input_unsupported(context, reason: str):
    profile = getattr(context, '_input_capability_profile', None)
    if not isinstance(profile, dict):
        profile = {}
        setattr(context, '_input_capability_profile', profile)
    profile['background_click'] = {'supported': False, 'reason': str(reason), 'updated_at': time.time()}
    try:
        from core.services.target_capability_profile import target_capability_profiles

        target_capability_profiles.record(context, 'background_click', False, reason)
    except Exception:
        pass


def mark_background_input_supported(context, reason: str = '点击后置验证通过'):
    profile = getattr(context, '_input_capability_profile', None)
    if not isinstance(profile, dict):
        profile = {}
        setattr(context, '_input_capability_profile', profile)
    profile['background_click'] = {'supported': True, 'reason': str(reason), 'updated_at': time.time()}
    try:
        from core.services.target_capability_profile import target_capability_profiles

        target_capability_profiles.record(context, 'background_click', True, reason)
    except Exception:
        pass
