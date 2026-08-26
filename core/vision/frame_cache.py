"""Per-context prepared representations for one immutable captured frame."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def prepared_frame(context: Any, image) -> dict[str, Any]:
    """Return RGB/BGR/gray arrays without converting the same PIL frame repeatedly."""

    token = id(image)
    cache = getattr(context, '_vision_frame_cache', None)
    if not isinstance(cache, dict) or cache.get('frame_token') != token:
        rgb = np.asarray(image.convert('RGB'))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cache = {
            'frame_token': token,
            'rgb': rgb,
            'bgr': bgr,
            'gray': cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY),
        }
        context._vision_frame_cache = cache
    return cache
