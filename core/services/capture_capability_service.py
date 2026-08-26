"""Explain and probe target capture tiers without hiding fallbacks."""

from __future__ import annotations

import importlib.util
import os
import platform
import time
from typing import Any


class CaptureCapabilityService:
    @staticmethod
    def environment() -> dict[str, Any]:
        from core.services.wgc_capture import WgcWindowSession

        wgc_available, wgc_detail = WgcWindowSession.available()
        return {
            'platform': platform.platform(),
            'windows_graphics_capture': {'available': wgc_available, 'detail': wgc_detail},
            'dxgi_desktop_duplication': {
                'available': importlib.util.find_spec('dxcam') is not None,
                'detail': '前台屏幕区域高速捕获；被其他窗口遮挡时只能得到遮挡后的桌面画面',
            },
            'print_window': {
                'available': os.name == 'nt',
                'detail': '标准 Win32 兼容层；GPU/自绘窗口即使 API 成功也可能是黑帧或旧帧',
            },
        }

    @classmethod
    def inspect_project(cls, project_path: str, *, probe: bool = False) -> dict[str, Any]:
        from core.services.workspace_service import WorkspaceService

        context = WorkspaceService.load_runtime_context(project_path)
        mode = str(context.get('work_mode') or ('window' if context.get('window_title') else 'desktop'))
        result: dict[str, Any] = {
            'mode': mode,
            'environment': cls.environment(),
            'target': {},
            'capture': {},
            'recommendation': '',
        }
        if mode == 'android' or bool(context.get('is_emulator')):
            serial = str(context.get('adb_device_id') or '').strip()
            try:
                from core.services.android_stream import validate_scrcpy_runtime

                stream_ok, detail = validate_scrcpy_runtime()
            except Exception as exc:
                stream_ok, detail = False, str(exc)
            result['target'] = {'kind': 'android', 'serial': serial}
            result['capture'] = {
                'grade': 'background_fresh' if serial and stream_ok else ('background_slow' if serial else 'unsupported'),
                'provider': 'scrcpy_stream' if stream_ok else ('adb_screencap' if serial else 'none'),
                'verified': bool(serial),
                'message': detail if stream_ok else (
                    'scrcpy 持续流不可用，将使用较慢的 ADB 单帧截图' if serial else '未绑定唯一 ADB serial'
                ),
            }
            result['recommendation'] = '高速视觉节点优先使用 scrcpy 持续流；普通节点可使用 ADB 单帧兜底。'
            return result

        if mode != 'window' or not context.get('window_title'):
            result['target'] = {'kind': 'desktop'}
            result['capture'] = {
                'grade': 'foreground_only', 'provider': 'dxgi_desktop_duplication', 'verified': True,
                'message': '桌面模式捕获屏幕实际可见像素，无法隔离被遮挡窗口。',
            }
            result['recommendation'] = '多开任务应绑定具体窗口，桌面模式只适合单前台场景。'
            return result

        try:
            import win32gui

            hwnd = WorkspaceService._resolve_context_window(context)
            minimized = bool(win32gui.IsIconic(hwnd))
            result['target'] = {
                'kind': 'window', 'hwnd': int(hwnd), 'title': win32gui.GetWindowText(hwnd),
                'minimized': minimized,
            }
            if minimized:
                result['capture'] = {
                    'grade': 'foreground_required', 'provider': 'none', 'verified': False,
                    'message': '目标窗口已最小化。WGC 官方行为不保证最小化窗口产出帧，请先还原窗口。',
                }
                result['recommendation'] = '还原但无需置顶；优先尝试 WGC 后台捕获。'
                return result
            if not probe:
                env = result['environment']
                wgc = env['windows_graphics_capture']['available']
                result['capture'] = {
                    'grade': 'background_candidate',
                    'provider': 'windows_graphics_capture' if wgc else 'print_window',
                    'verified': False,
                    'message': '尚未取样验证；运行环境只代表 API 可用，不代表目标窗口允许捕获。',
                }
                result['recommendation'] = '执行一次能力检测，记录该窗口类别的实际捕获结果。'
                return result

            from core.services.screenshot_service import capture_window_with_info

            started = time.perf_counter()
            image, info = capture_window_with_info(hwnd)
            if image is None:
                result['capture'] = info
                result['recommendation'] = '运行时激活到前台后使用 DXGI；如仍为黑屏，应判定保护画面/不支持。'
                return result
            extrema = image.convert('L').getextrema()
            health = 'black' if extrema and extrema[1] <= 2 else ('uniform' if extrema and extrema[1] - extrema[0] <= 2 else 'normal')
            info = {**info, 'width': image.width, 'height': image.height, 'frame_health': health,
                    'probe_duration_ms': round((time.perf_counter() - started) * 1000, 2)}
            if health == 'black':
                info.update({'grade': 'foreground_required', 'verified': False,
                             'message': f'{info.get("provider")} 返回全黑帧'})
            else:
                info['grade'] = info.pop('capability', 'background_unverified')
            result['capture'] = info
            result['recommendation'] = (
                '可后台识别；首次输入后仍应使用视觉后置条件验证效果。'
                if info.get('grade') == 'background_fresh'
                else '后台画面未完全验证，失败时激活窗口使用 DXGI。'
            )
            return result
        except Exception as exc:
            result['capture'] = {'grade': 'unsupported', 'provider': 'none', 'verified': False, 'message': str(exc)}
            result['recommendation'] = '检查窗口绑定；禁止静默回退到无关桌面画面。'
            return result


capture_capability_service = CaptureCapabilityService()

