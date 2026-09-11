"""Pure pixel adapters shared by live format-6 vision and offline replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class TemplateMatchV6:
    region: tuple[int, int, int, int]
    similarity: float

    @property
    def center(self) -> tuple[int, int]:
        x, y, width, height = self.region
        return x + width // 2, y + height // 2


@dataclass(frozen=True)
class TemplateMatchAnalysisV6:
    """One-pass match result, including evidence below the author threshold."""

    matches: tuple[TemplateMatchV6, ...]
    best_similarity: float | None


def frame_to_bgr(frame: Any, *, frame_is_bgr: bool) -> np.ndarray:
    """Normalize Pillow/numpy frames without mutating the captured pixels."""

    image = np.asarray(frame)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim != 3 or image.shape[2] not in {3, 4}:
        raise ValueError("画面不是受支持的灰度、RGB/BGR 或 RGBA/BGRA 图像")
    if image.shape[2] == 4:
        code = cv2.COLOR_BGRA2BGR if frame_is_bgr else cv2.COLOR_RGBA2BGR
        return cv2.cvtColor(image, code)
    if frame_is_bgr:
        return image
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def _intersection_over_union(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    x1, y1 = max(lx, rx), max(ly, ry)
    x2, y2 = min(lx + lw, rx + rw), min(ly + lh, ry + rh)
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection <= 0:
        return 0.0
    return intersection / float(lw * lh + rw * rh - intersection)


def analyze_template_matches(
    frame: Any,
    prepared_variants: Any,
    *,
    threshold: float,
    limit: int,
    offset_x: int = 0,
    offset_y: int = 0,
    frame_is_bgr: bool = False,
) -> TemplateMatchAnalysisV6:
    """Find deterministic, de-duplicated matches across prepared scales.

    The candidate cap bounds pathological low-threshold or repeated-background
    inputs before NMS.  Results are ordered by similarity, then geometry.
    """

    screen = frame_to_bgr(frame, frame_is_bgr=frame_is_bgr)
    screen_height, screen_width = screen.shape[:2]
    candidate_cap = min(20_000, max(1_000, int(limit) * 80))
    candidates: list[TemplateMatchV6] = []
    best_similarity: float | None = None
    for raw_width, raw_height, raw_template in prepared_variants:
        width, height = int(raw_width), int(raw_height)
        if width < 2 or height < 2 or width > screen_width or height > screen_height:
            continue
        template = np.asarray(raw_template)
        if template.ndim == 2:
            template = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
        elif template.ndim == 3 and template.shape[2] == 4:
            template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
        response = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        finite = np.isfinite(response)
        if np.any(finite):
            variant_best = float(np.max(response[finite]))
            best_similarity = variant_best if best_similarity is None else max(best_similarity, variant_best)
        eligible = finite & (response >= float(threshold))
        if not np.any(eligible):
            continue
        # Keep one local maximum for a small response neighbourhood before the
        # cross-scale NMS pass. This avoids turning one match into hundreds of
        # adjacent candidates while preserving nearby distinct objects.
        local_max = response >= cv2.dilate(response, np.ones((3, 3), np.uint8))
        ys, xs = np.nonzero(eligible & local_max)
        scores = response[ys, xs]
        if scores.size > candidate_cap:
            selected = np.argpartition(scores, -candidate_cap)[-candidate_cap:]
            ys, xs, scores = ys[selected], xs[selected], scores[selected]
        for x, y, score in zip(xs.tolist(), ys.tolist(), scores.tolist(), strict=True):
            candidates.append(TemplateMatchV6(
                region=(int(x + offset_x), int(y + offset_y), width, height),
                similarity=float(score),
            ))

    candidates.sort(key=lambda item: (
        -item.similarity,
        item.region[1],
        item.region[0],
        item.region[3],
        item.region[2],
    ))
    accepted: list[TemplateMatchV6] = []
    for candidate in candidates:
        if any(_intersection_over_union(candidate.region, item.region) >= 0.30 for item in accepted):
            continue
        accepted.append(candidate)
        if len(accepted) >= int(limit):
            break
    return TemplateMatchAnalysisV6(tuple(accepted), best_similarity)


def find_template_matches(
    frame: Any,
    prepared_variants: Any,
    *,
    threshold: float,
    limit: int,
    offset_x: int = 0,
    offset_y: int = 0,
    frame_is_bgr: bool = False,
) -> list[TemplateMatchV6]:
    """Compatibility wrapper for callers that only need accepted matches."""

    return list(analyze_template_matches(
        frame,
        prepared_variants,
        threshold=threshold,
        limit=limit,
        offset_x=offset_x,
        offset_y=offset_y,
        frame_is_bgr=frame_is_bgr,
    ).matches)


__all__ = [
    "TemplateMatchAnalysisV6", "TemplateMatchV6", "analyze_template_matches",
    "find_template_matches", "frame_to_bgr",
]
