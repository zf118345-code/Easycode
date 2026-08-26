# core/services/workspace_service.py
import base64
import ctypes
import io
import json
import os
import re
import subprocess
import time

import pyautogui
from core.services import screenshot_service
import win32con
import win32gui
import win32process
from fastapi import HTTPException

from core.schemas import ContextSaveRequestSchema
from core.project_schema import PROJECT_SCHEMA_VERSION
from core.security import assert_safe_path, atomic_write_json
from core.services.asset_service import AssetService

CONTEXT_FILE = 'context.json'


def get_unicode_window_text(hwnd: int) -> str:
    """使用 Windows 原生 GetWindowTextW 读取 Unicode 字符串，防止 GBK/ANSI 中文乱码"""
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    return ''


class WorkspaceService:
    _MIN_CAPTURE_EDGE = 32

    @staticmethod
    def _require_captureable_window(hwnd: int) -> int:
        """Reject minimized shells before reading geometry or pixels.

        PrintWindow behavior for minimized GPU/custom-rendered windows is not a
        capability guarantee: many applications return a black client surface,
        a stale frame, or only a narrow non-client strip.  Capture mode is an
        editing tool and must not silently restore the user's target window.
        """
        root = win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd
        if win32gui.IsIconic(root):
            raise HTTPException(
                status_code=409,
                detail='目标工作窗口已最小化，请先还原窗口后再进入截图捕获模式',
            )
        return int(root)

    @classmethod
    def _validate_capture_size(cls, width: int, height: int) -> None:
        if width < cls._MIN_CAPTURE_EDGE or height < cls._MIN_CAPTURE_EDGE:
            raise HTTPException(
                status_code=409,
                detail=f'捕获到的工作面板尺寸异常（{width}×{height}），请确认窗口已还原且裁剪范围有效',
            )

    @staticmethod
    def _window_workspace_box(hwnd: int, ctx: dict) -> tuple[int, int, int, int]:
        client = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
        box = (
            left + int(ctx.get('offset_left', 0) or 0),
            top + int(ctx.get('offset_top', 0) or 0),
            right - int(ctx.get('offset_right', 0) or 0),
            bottom - int(ctx.get('offset_bottom', 0) or 0),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            raise HTTPException(status_code=400, detail=f'裁剪后的工作区无效: {box}')
        return box

    @staticmethod
    def _wait_window_geometry(hwnd: int, ctx: dict, timeout: float = 1.0) -> tuple[int, int, int, int]:
        """Two equal geometry probes are enough; animated pixels are deliberately ignored."""
        deadline = time.monotonic() + max(0.2, timeout)
        previous = None
        stable = 0
        while time.monotonic() < deadline:
            current = WorkspaceService._window_workspace_box(hwnd, ctx)
            if current == previous:
                stable += 1
                if stable >= 1:
                    return current
            else:
                previous = current
                stable = 0
            time.sleep(0.06)
        raise HTTPException(status_code=409, detail='目标工作面板的位置或尺寸仍在变化，请稍后重试')

    @staticmethod
    def _visible_window_capture(hwnd: int, ctx: dict):
        """Foreground fallback used only when reliable background capture is unavailable."""
        from core.services.frame_recording_service import FrameRecordingService

        previous_foreground = win32gui.GetForegroundWindow()
        target_root = win32gui.GetAncestor(hwnd, getattr(win32con, 'GA_ROOT', 2)) or hwnd
        was_iconic = bool(win32gui.IsIconic(target_root))
        previous_above = win32gui.GetWindow(target_root, win32con.GW_HWNDPREV)
        try:
            FrameRecordingService._activate_target(ctx)
            box = WorkspaceService._wait_window_geometry(hwnd, ctx)
            target_pid = int(win32process.GetWindowThreadProcessId(target_root)[1])
            current = win32gui.GetTopWindow(None)
            while current and int(current) != int(target_root):
                try:
                    if win32gui.IsWindowVisible(current) and not win32gui.IsIconic(current):
                        current_pid = int(win32process.GetWindowThreadProcessId(current)[1])
                        if current_pid != target_pid:
                            left, top, right, bottom = win32gui.GetWindowRect(current)
                            intersects = (
                                min(box[2], right) > max(box[0], left)
                                and min(box[3], bottom) > max(box[1], top)
                            )
                            if intersects:
                                raise HTTPException(
                                    status_code=409,
                                    detail='目标窗口仍被其他置顶窗口遮挡，无法获得完整截图',
                                )
                except HTTPException:
                    raise
                except Exception:
                    pass
                current = win32gui.GetWindow(current, win32con.GW_HWNDNEXT)
            points = [
                ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
                (box[0] + 2, box[1] + 2),
                (box[2] - 3, box[1] + 2),
                (box[0] + 2, box[3] - 3),
                (box[2] - 3, box[3] - 3),
            ]
            for point in points:
                hit = win32gui.WindowFromPoint(point)
                if not hit:
                    raise HTTPException(status_code=409, detail='无法确认工作面板未被遮挡')
                hit_root = win32gui.GetAncestor(hit, getattr(win32con, 'GA_ROOT', 2)) or hit
                hit_pid = int(win32process.GetWindowThreadProcessId(hit_root)[1])
                if hit_pid != target_pid:
                    raise HTTPException(status_code=409, detail='目标窗口仍被其他窗口遮挡，无法获得完整截图')
            image = screenshot_service.capture(region=box).convert('RGB')
            WorkspaceService._validate_capture_size(image.width, image.height)
            return image, list(box)
        finally:
            if win32gui.IsWindow(target_root):
                try:
                    win32gui.SetWindowPos(
                        target_root,
                        previous_above if previous_above and win32gui.IsWindow(previous_above) else win32con.HWND_BOTTOM,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                    )
                except Exception:
                    pass
            if was_iconic and win32gui.IsWindow(target_root):
                try:
                    win32gui.ShowWindow(target_root, win32con.SW_MINIMIZE)
                except Exception:
                    pass
            if previous_foreground and win32gui.IsWindow(previous_foreground):
                try:
                    win32gui.SetForegroundWindow(previous_foreground)
                except Exception:
                    pass

    @staticmethod
    def get_windows() -> dict:
        windows = []
        IGNORE_TITLES = {
            'Program Manager',
            'Windows 输入体验',
            'Windows Input Experience',
            '新通知',
            '通知中心',
            '设置',
            'Settings',
        }

        def callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = get_unicode_window_text(hwnd)
            if not title or title in IGNORE_TITLES:
                return

            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if (ex_style & win32con.WS_EX_TOOLWINDOW) and not (ex_style & win32con.WS_EX_APPWINDOW):
                return

            try:
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w < 100 or h < 100 or rect[2] <= 0 or rect[3] <= 0:
                    return

                client_rect = win32gui.GetClientRect(hwnd)
                client_w = client_rect[2] - client_rect[0]
                client_h = client_rect[3] - client_rect[1]
                if client_w <= 0 or client_h <= 0:
                    return

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                windows.append(
                    {'hwnd': hwnd, 'title': title, 'process_id': pid, 'class_name': win32gui.GetClassName(hwnd)}
                )
            except Exception:
                pass

        win32gui.EnumWindows(callback, None)
        return {'windows': windows}

    @staticmethod
    def resolve_adb_device(window_title: str = '', window_hwnd: int = 0, process_id: int = 0) -> dict:
        """Resolve a selected emulator window to one online ADB device.

        A single online device is deterministic. With multiple devices we use
        explicit serial/port tokens in the title first, then score stable ADB
        properties against the selected window title. Ambiguous matches are
        rejected: choosing the wrong emulator instance is worse than disabling
        emulator mode.
        """
        title = str(window_title or '').strip()
        if window_hwnd:
            try:
                actual = get_unicode_window_text(int(window_hwnd))
                if actual:
                    title = actual
            except Exception:
                pass
        try:
            result = subprocess.run(
                ['adb', 'devices'], capture_output=True, text=True, timeout=4,
                encoding='utf-8', errors='ignore',
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f'无法调用 ADB：{exc}') from exc
        if result.returncode != 0:
            raise HTTPException(status_code=409, detail=f'ADB 设备枚举失败：{(result.stderr or result.stdout).strip()}')
        devices = []
        for line in (result.stdout or '').splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
        if not devices:
            raise HTTPException(status_code=409, detail='未发现在线 ADB 模拟器，请先启动模拟器的 ADB 调试服务')
        if len(devices) == 1:
            return {'status': 'success', 'serial': devices[0], 'method': 'single_online_device', 'window_title': title}

        normalized_title = title.casefold()
        port_tokens = set(re.findall(r'(?:emulator-|(?:127\.0\.0\.1|localhost):)(\d{4,5})', normalized_title))
        if port_tokens:
            matches = [serial for serial in devices if any(token in serial for token in port_tokens)]
            if len(matches) == 1:
                return {'status': 'success', 'serial': matches[0], 'method': 'title_port', 'window_title': title}

        scored = []
        properties = ['ro.boot.qemu.avd_name', 'ro.product.model', 'ro.product.name', 'ro.product.brand']
        for serial in devices:
            tokens = []
            for prop in properties:
                try:
                    probe = subprocess.run(
                        ['adb', '-s', serial, 'shell', 'getprop', prop],
                        capture_output=True, text=True, timeout=2,
                        encoding='utf-8', errors='ignore',
                    )
                    value = (probe.stdout or '').strip().casefold()
                    if value and value not in {'unknown', 'android'}:
                        tokens.append(value)
                except Exception:
                    continue
            score = sum(max(1, len(token)) for token in set(tokens) if token in normalized_title)
            scored.append((score, serial, tokens))
        scored.sort(reverse=True)
        if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return {'status': 'success', 'serial': scored[0][1], 'method': 'window_title_property', 'window_title': title}
        raise HTTPException(
            status_code=409,
            detail=f'当前有 {len(devices)} 个在线 ADB 设备，无法根据窗口标题「{title or "未命名窗口"}」唯一匹配。已退出模拟器模式以避免点错实例。',
        )

    @staticmethod
    def get_adb_devices() -> dict:
        """Enumerate real devices and emulators as first-class Android targets."""
        try:
            result = subprocess.run(
                ['adb', 'devices', '-l'], capture_output=True, text=True, timeout=4,
                encoding='utf-8', errors='ignore',
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f'无法调用 ADB：{exc}') from exc
        if result.returncode != 0:
            raise HTTPException(status_code=409, detail=f'ADB 设备枚举失败：{(result.stderr or result.stdout).strip()}')

        devices = []
        for line in (result.stdout or '').splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            metadata = {}
            for token in parts[2:]:
                key, separator, value = token.partition(':')
                if separator:
                    metadata[key] = value
            width = height = 0
            natural_width = natural_height = 0
            rotation = 0
            android_version = ''
            if state == 'device':
                try:
                    size_result = subprocess.run(
                        ['adb', '-s', serial, 'shell', 'wm', 'size'],
                        capture_output=True, text=True, timeout=2,
                        encoding='utf-8', errors='ignore',
                    )
                    matches = re.findall(r'(\d+)x(\d+)', size_result.stdout or '')
                    if matches:
                        natural_width, natural_height = (int(value) for value in matches[-1])
                        width, height = natural_width, natural_height
                except Exception:
                    pass
                try:
                    orientation_result = subprocess.run(
                        ['adb', '-s', serial, 'shell', 'dumpsys', 'input'],
                        capture_output=True, text=True, timeout=3,
                        encoding='utf-8', errors='ignore',
                    )
                    orientation_text = orientation_result.stdout or ''
                    viewport_match = re.search(
                        r'DisplayViewport\[id=0\][\s\S]{0,240}?Width=(\d+),\s*Height=(\d+)',
                        orientation_text,
                        flags=re.IGNORECASE,
                    )
                    orientation_match = re.search(
                        r'(?:SurfaceOrientation\s*:\s*|orientation\s*[:=]\s*)([0-3])',
                        orientation_text,
                        flags=re.IGNORECASE,
                    )
                    if orientation_match:
                        rotation = int(orientation_match.group(1))
                    if viewport_match:
                        width, height = (int(value) for value in viewport_match.groups())
                    elif rotation % 2 == 1 and width and height:
                        width, height = height, width
                except Exception:
                    pass
                try:
                    version_result = subprocess.run(
                        ['adb', '-s', serial, 'shell', 'getprop', 'ro.build.version.release'],
                        capture_output=True, text=True, timeout=2,
                        encoding='utf-8', errors='ignore',
                    )
                    android_version = (version_result.stdout or '').strip()
                except Exception:
                    pass
            devices.append({
                'serial': serial,
                'state': state,
                'model': metadata.get('model', '').replace('_', ' '),
                'product': metadata.get('product', ''),
                'device': metadata.get('device', ''),
                'transport_id': metadata.get('transport_id', ''),
                'android_version': android_version,
                'width': width,
                'height': height,
                'natural_width': natural_width,
                'natural_height': natural_height,
                'rotation': rotation,
                'kind': 'emulator' if serial.startswith('emulator-') or ':' in serial else 'physical',
                'capture_tier': 'scrcpy_latest_frame',
                'input_tier': 'scrcpy_control_with_adb_fallback',
            })
        return {'devices': devices}

    @staticmethod
    def save_context(request: ContextSaveRequestSchema) -> dict:
        context = request.context
        portable_context = {
            'schema_version': PROJECT_SCHEMA_VERSION,
            'work_mode': context.get('workMode', 'window'),
            'is_emulator': context.get('isEmulator', False),
            'is_android': context.get('workMode') == 'android' or context.get('isAndroid', False),
            'offset_top': context.get('offsetTop', 0),
            'offset_bottom': context.get('offsetBottom', 0),
            'offset_left': context.get('offsetLeft', 0),
            'offset_right': context.get('offsetRight', 0),
            'target_content_width': context.get('targetContentWidth', 0),
            'target_content_height': context.get('targetContentHeight', 0),
        }
        context_path = os.path.join(request.project_path, CONTEXT_FILE)
        previous_portable = None
        if os.path.isfile(context_path):
            try:
                with open(context_path, encoding='utf-8-sig') as stream:
                    previous_portable = json.load(stream)
            except (OSError, json.JSONDecodeError):
                previous_portable = None
        local_path = os.path.join(request.project_path, '.easycode', 'local-settings.json')
        local_settings = {
            'schema_version': PROJECT_SCHEMA_VERSION,
            'context_binding': {
                'window_title': context.get('windowTitle', ''),
                'window_hwnd': int(context.get('windowHwnd', 0) or 0),
                'window_process_id': int(context.get('windowProcessId', 0) or 0),
                'window_class_name': context.get('windowClassName', ''),
                'adb_device_id': context.get('adbDeviceId', ''),
            },
        }
        atomic_write_json(context_path, portable_context)
        atomic_write_json(local_path, local_settings)
        revision = None
        if previous_portable != portable_context:
            from core.services.blueprint_service import BlueprintService

            meta = BlueprintService.load_project_meta(request.project_path)
            BlueprintService.save_project_meta(
                request.project_path,
                meta,
                create_snapshot=True,
                snapshot_reason='save_context',
            )
            revision = int(meta.get('revision', 0)) + 1
        return {'status': 'success', 'revision': revision}

    @staticmethod
    def load_runtime_context(project_path: str) -> dict:
        context_path = os.path.join(project_path, CONTEXT_FILE)
        if not os.path.exists(context_path):
            return {}
        with open(context_path, encoding='utf-8') as f:
            data = json.load(f)
        local_path = os.path.join(project_path, '.easycode', 'local-settings.json')
        if os.path.isfile(local_path):
            try:
                with open(local_path, encoding='utf-8-sig') as stream:
                    local = json.load(stream)
                binding = local.get('context_binding') if isinstance(local, dict) else None
                if isinstance(binding, dict):
                    data = {**data, **binding}
            except (OSError, json.JSONDecodeError):
                pass
        return data

    @staticmethod
    def get_context(project_path: str) -> dict:
        data = WorkspaceService.load_runtime_context(project_path)

        return {
            'workMode': data.get('work_mode') or ('window' if data.get('window_title') else 'desktop'),
            'windowTitle': data.get('window_title', ''),
            'windowHwnd': data.get('window_hwnd', 0),
            'windowProcessId': data.get('window_process_id', 0),
            'windowClassName': data.get('window_class_name', ''),
            'isEmulator': data.get('is_emulator', False),
            'isAndroid': data.get('is_android', False) or data.get('work_mode') == 'android',
            'adbDeviceId': data.get('adb_device_id', ''),
            'offsetTop': data.get('offset_top', 0),
            'offsetBottom': data.get('offset_bottom', 0),
            'offsetLeft': data.get('offset_left', 0),
            'offsetRight': data.get('offset_right', 0),
            'targetContentWidth': data.get('target_content_width', 0),
            'targetContentHeight': data.get('target_content_height', 0),
        }

    @staticmethod
    def _resolve_context_window(ctx: dict) -> int:
        """按保存的实例身份解析窗口；同名歧义时拒绝猜测。"""
        title = str(ctx.get('window_title') or '').strip()
        expected_hwnd = int(ctx.get('window_hwnd', 0) or 0)
        expected_pid = int(ctx.get('window_process_id', 0) or 0)
        expected_class = str(ctx.get('window_class_name') or '')

        def matches(hwnd):
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return (
                get_unicode_window_text(hwnd) == title
                and (not expected_pid or int(pid) == expected_pid)
                and (not expected_class or win32gui.GetClassName(hwnd) == expected_class)
            )

        if matches(expected_hwnd):
            return expected_hwnd

        candidates = []

        def callback(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd) or get_unicode_window_text(hwnd) != title:
                    return
                if expected_class and win32gui.GetClassName(hwnd) != expected_class:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                candidates.append((hwnd, int(pid)))
            except Exception:
                return

        win32gui.EnumWindows(callback, None)
        if expected_pid:
            pid_matches = [item for item in candidates if item[1] == expected_pid]
            if len(pid_matches) == 1:
                return int(pid_matches[0][0])
        if len(candidates) == 1:
            return int(candidates[0][0])
        if not candidates:
            raise HTTPException(status_code=404, detail=f'未找到已配置的目标窗口: {title}')
        raise HTTPException(status_code=409, detail=f'存在多个同名窗口“{title}”，请重新选择具体实例')

    @staticmethod
    def _capture_context_image(ctx: dict):
        """捕获与运行目标相同的画面；绑定失败时不回退全屏。"""
        work_mode = str(ctx.get('work_mode') or ('window' if ctx.get('window_title') else 'desktop'))
        off_top = int(ctx.get('offset_top', 0) or 0)
        off_bottom = int(ctx.get('offset_bottom', 0) or 0)
        off_left = int(ctx.get('offset_left', 0) or 0)
        off_right = int(ctx.get('offset_right', 0) or 0)

        if work_mode == 'android':
            serial = str(ctx.get('adb_device_id') or '').strip()
            if not serial:
                raise HTTPException(status_code=409, detail='Android目标未绑定 ADB 设备')
            try:
                result = subprocess.run(
                    ['adb', '-s', serial, 'exec-out', 'screencap', '-p'],
                    capture_output=True,
                    timeout=8,
                )
            except Exception as exc:
                raise HTTPException(status_code=409, detail=f'Android截图异常: {exc}') from exc
            if result.returncode != 0 or not result.stdout:
                detail = result.stderr.decode(errors='ignore').strip() if result.stderr else '无图像数据'
                raise HTTPException(status_code=409, detail=f'Android截图失败: {detail}')
            from PIL import Image

            try:
                image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
                image.load()
            except Exception as exc:
                raise HTTPException(status_code=409, detail=f'Android截图无法解码: {exc}') from exc
            target_w = int(ctx.get('target_content_width', 0) or 0)
            target_h = int(ctx.get('target_content_height', 0) or 0)
            if target_w > 0 and target_h > 0 and image.size != (target_w, target_h):
                image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
            WorkspaceService._validate_capture_size(image.width, image.height)
            return image, [0, 0, image.width, image.height]

        if work_mode == 'window' and ctx.get('window_title'):
            hwnd = WorkspaceService._resolve_context_window(ctx)
            WorkspaceService._require_captureable_window(hwnd)
            screen_box = WorkspaceService._wait_window_geometry(hwnd, ctx)
            WorkspaceService._validate_capture_size(
                screen_box[2] - screen_box[0],
                screen_box[3] - screen_box[1],
            )
            if bool(ctx.get('is_emulator')):
                serial = str(ctx.get('adb_device_id') or '').strip()
                if not serial:
                    raise HTTPException(status_code=409, detail='模拟器未绑定唯一 ADB serial')
                try:
                    result = subprocess.run(
                        ['adb', '-s', serial, 'exec-out', 'screencap', '-p'],
                        capture_output=True,
                        timeout=8,
                    )
                except Exception as exc:
                    raise HTTPException(status_code=409, detail=f'ADB 截图异常: {exc}') from exc
                if result.returncode != 0 or not result.stdout:
                    detail = result.stderr.decode(errors='ignore').strip() if result.stderr else '无图像数据'
                    raise HTTPException(status_code=409, detail=f'ADB 截图失败: {detail}')
                from PIL import Image

                try:
                    image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
                    image.load()
                except Exception as exc:
                    raise HTTPException(status_code=409, detail=f'ADB 截图无法解码: {exc}') from exc
                region = [0, 0, image.width, image.height]
                # ADB exposes device pixels while the IDE coordinate contract is the
                # configured/cropped work-panel size.  Display and capture nodes must
                # therefore use the latter consistently.
                target_w = int(ctx.get('target_content_width', 0) or 0)
                target_h = int(ctx.get('target_content_height', 0) or 0)
                region = list(screen_box)
                if target_w <= 0:
                    target_w = screen_box[2] - screen_box[0]
                if target_h <= 0:
                    target_h = screen_box[3] - screen_box[1]
                if target_w > 0 and target_h > 0 and image.size != (target_w, target_h):
                    from PIL import Image as PILImage

                    image = image.resize((target_w, target_h), PILImage.Resampling.LANCZOS)
                WorkspaceService._validate_capture_size(image.width, image.height)
                return image, region

            full = screenshot_service.capture_window(hwnd)
            if full is None:
                return WorkspaceService._visible_window_capture(hwnd, ctx)
            try:
                cropped = screenshot_service.crop_window_image(hwnd, full, screen_box)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            WorkspaceService._validate_capture_size(cropped.width, cropped.height)
            extrema = cropped.convert('L').getextrema()
            if extrema and extrema[1] <= 2:
                return WorkspaceService._visible_window_capture(hwnd, ctx)
            return cropped, list(screen_box)

        screen_w, screen_h = pyautogui.size()
        region = (off_left, off_top, screen_w - off_right, screen_h - off_bottom)
        if region[2] <= region[0] or region[3] <= region[1]:
            raise HTTPException(status_code=400, detail=f'裁剪后的桌面工作区无效: {region}')
        return screenshot_service.capture(region=region).convert('RGB'), list(region)

    @staticmethod
    def get_full_screenshot(project_path: str = '') -> dict:
        ctx = {}
        if project_path:
            ctx = WorkspaceService.load_runtime_context(project_path)

        screenshot, region = WorkspaceService._capture_context_image(ctx)
        buffer = io.BytesIO()
        screenshot.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            'image': img_str,
            'width': screenshot.width,
            'height': screenshot.height,
            'region': region,
        }

    @staticmethod
    def crop_screenshot(project_path: str, template_name: str, crop_rect: list[int]) -> dict:
        """
        ⚡ 统一截图落盘服务 (遵循沙箱越界安全规范)
        支持在 templates/ 及其任意子目录下 (如 templates/ocr/) 裁剪与保存图片
        """
        templates_dir = os.path.join(project_path, 'templates')
        os.makedirs(templates_dir, exist_ok=True)

        clean_key = template_name.replace('.png', '').replace('.PNG', '').replace('\\', '/')

        # ⚡ 工业级安全路径修复：先通过 os.path.join 拼出完整的目标绝对路径，再提交安全防越界校验
        full_target_path = os.path.join(templates_dir, f'{clean_key}.png')
        save_path = assert_safe_path(templates_dir, full_target_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        rel_x, rel_y, w, h = [int(value) for value in crop_rect]
        ctx = WorkspaceService.load_runtime_context(project_path)
        source, _ = WorkspaceService._capture_context_image(ctx)
        if rel_x < 0 or rel_y < 0 or w <= 0 or h <= 0 or rel_x + w > source.width or rel_y + h > source.height:
            raise HTTPException(status_code=400, detail='模板裁剪区域超出当前工作区')
        cropped_img = source.crop((rel_x, rel_y, rel_x + w, rel_y + h))
        cropped_img.save(save_path)

        record = AssetService.register_file(
            project_path,
            f'{clean_key}.png',
            capture={
                'region': crop_rect,
                'reference_size': [source.width, source.height],
                'coordinate_space': 'workspace_px',
            },
        )

        return {
            'status': 'success',
            'file_path': save_path,
            'key': clean_key,
            'asset_id': record['id'],
            'asset_ref': AssetService.reference(record['id']),
        }

    @staticmethod
    def capture_frozen_snapshot(project_path: str) -> dict:
        """Capture once and return immutable PNG bytes plus coordinate metadata."""
        context_path = os.path.join(project_path, CONTEXT_FILE)
        if not os.path.isfile(context_path):
            raise HTTPException(status_code=409, detail='项目尚未配置工作面板')
        ctx = WorkspaceService.load_runtime_context(project_path)
        screenshot, region = WorkspaceService._capture_context_image(ctx)
        buffer = io.BytesIO()
        screenshot.save(buffer, format='PNG')
        if bool(ctx.get('is_emulator')):
            backend = 'adb'
        elif str(ctx.get('work_mode') or '') == 'window':
            backend = 'window'
        else:
            backend = 'desktop'
        return {
            '_png': buffer.getvalue(),
            'width': screenshot.width,
            'height': screenshot.height,
            'region': region,
            'backend': backend,
        }
