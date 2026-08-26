"""Probe the exact Windows capture tier EasyCode will use for a live window."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if os.fspath(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(PROJECT_ROOT))

from core.services.screenshot_service import capture_window_with_info
from core.services.wgc_capture import wgc_sessions


def windows() -> list[dict]:
    import win32gui

    result = []

    def visit(hwnd, _extra):
        try:
            title = win32gui.GetWindowText(hwnd).strip()
            rect = win32gui.GetWindowRect(hwnd)
            width, height = rect[2] - rect[0], rect[3] - rect[1]
            if title and win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd) and width >= 240 and height >= 160:
                result.append({'hwnd': int(hwnd), 'title': title, 'width': width, 'height': height})
        except Exception:
            pass
        return True

    win32gui.EnumWindows(visit, None)
    return result


def probe(title_contains: str, frame_count: int) -> dict:
    candidates = windows()
    needle = str(title_contains or '').casefold()
    candidate = next((item for item in candidates if needle and needle in item['title'].casefold()), None)
    candidate = candidate or next((item for item in candidates if item['title'] != 'Program Manager'), None)
    if not candidate:
        raise RuntimeError('没有找到可见且未最小化的候选窗口')
    frames = []
    try:
        for _ in range(max(1, min(60, frame_count))):
            started = time.perf_counter()
            image, info = capture_window_with_info(candidate['hwnd'])
            if image is None:
                frames.append({'ok': False, 'info': info})
                break
            grayscale = image.convert('L')
            extrema = grayscale.getextrema()
            frames.append({
                'ok': True,
                'size': list(image.size),
                'health': 'black' if extrema and extrema[1] <= 2 else ('uniform' if extrema and extrema[1] - extrema[0] <= 2 else 'normal'),
                'sha256': hashlib.sha256(image.tobytes()).hexdigest()[:16],
                'wall_ms': round((time.perf_counter() - started) * 1000, 2),
                'info': info,
            })
            time.sleep(0.03)
    finally:
        wgc_sessions.discard(candidate['hwnd'])
    successful = [item for item in frames if item['ok']]
    return {
        'target': candidate,
        'candidate_count': len(candidates),
        'frames': frames,
        'summary': {
            'successful_frames': len(successful),
            'provider': successful[-1]['info'].get('provider') if successful else 'none',
            'normal_frames': sum(1 for item in successful if item['health'] == 'normal'),
            'average_wall_ms': round(sum(item['wall_ms'] for item in successful) / len(successful), 2) if successful else 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', default='')
    parser.add_argument('--frames', type=int, default=3)
    args = parser.parse_args()
    result = probe(args.title, args.frames)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['summary']['normal_frames'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
