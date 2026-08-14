# core/services/workspace_service.py
import base64
import ctypes
import io
import json
import os

import pyautogui
import win32con
import win32gui
import win32process
from fastapi import HTTPException

from core.schemas import ContextSaveRequestSchema
from core.security import assert_safe_path, atomic_write_json
from core.services.vision_service import VisionService

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
    @staticmethod
    def get_windows() -> dict:
        windows = []
        seen_titles = set()
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
                if title in seen_titles:
                    return
                seen_titles.add(title)

                windows.append(
                    {'hwnd': hwnd, 'title': title, 'process_id': pid, 'class_name': win32gui.GetClassName(hwnd)}
                )
            except Exception:
                pass

        win32gui.EnumWindows(callback, None)
        return {'windows': windows}

    @staticmethod
    def save_context(request: ContextSaveRequestSchema) -> dict:
        context = request.context
        mapped_context = {
            'window_title': context.get('windowTitle', ''),
            'is_emulator': context.get('isEmulator', False),
            'offset_top': context.get('offsetTop', 0),
            'offset_bottom': context.get('offsetBottom', 0),
            'offset_left': context.get('offsetLeft', 0),
            'offset_right': context.get('offsetRight', 0),
            'target_content_width': context.get('targetContentWidth', 0),
            'target_content_height': context.get('targetContentHeight', 0),
        }
        context_path = os.path.join(request.project_path, CONTEXT_FILE)
        atomic_write_json(context_path, mapped_context)
        return {'status': 'success'}

    @staticmethod
    def get_context(project_path: str) -> dict:
        context_path = os.path.join(project_path, CONTEXT_FILE)
        if not os.path.exists(context_path):
            return {}
        with open(context_path, encoding='utf-8') as f:
            data = json.load(f)

        return {
            'windowTitle': data.get('window_title', ''),
            'isEmulator': data.get('is_emulator', False),
            'offsetTop': data.get('offset_top', 0),
            'offsetBottom': data.get('offset_bottom', 0),
            'offsetLeft': data.get('offset_left', 0),
            'offsetRight': data.get('offset_right', 0),
            'targetContentWidth': data.get('target_content_width', 0),
            'targetContentHeight': data.get('target_content_height', 0),
        }

    @staticmethod
    def get_full_screenshot(project_path: str = '') -> dict:
        region = None
        if project_path:
            context_path = os.path.join(project_path, CONTEXT_FILE)
            if os.path.exists(context_path):
                try:
                    with open(context_path, encoding='utf-8') as f:
                        ctx = json.load(f)
                    window_title = ctx.get('window_title')
                    if window_title:
                        hwnd = win32gui.FindWindow(None, window_title)
                        if hwnd:
                            client_rect = win32gui.GetClientRect(hwnd)
                            left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                            right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

                            off_top, off_bottom = ctx.get('offset_top', 0), ctx.get('offset_bottom', 0)
                            off_left, off_right = ctx.get('offset_left', 0), ctx.get('offset_right', 0)

                            x = left + off_left
                            y = top + off_top
                            w = (right - left) - off_left - off_right
                            h = (bottom - top) - off_bottom - off_bottom

                            if w > 0 and h > 0:
                                region = (x, y, w, h)
                except Exception as e:
                    print(f'读取工作区失败: {e}')

        screenshot = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
        buffer = io.BytesIO()
        screenshot.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return {
            'image': img_str,
            'width': screenshot.width,
            'height': screenshot.height,
            'region': region or [0, 0, pyautogui.size()[0], pyautogui.size()[1]],
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

        rel_x, rel_y, w, h = crop_rect
        context_path = os.path.join(project_path, CONTEXT_FILE)
        abs_x, abs_y = rel_x, rel_y

        if os.path.exists(context_path):
            with open(context_path, encoding='utf-8') as f:
                ctx = json.load(f)
            window_title = ctx.get('window_title')
            if window_title:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd:
                    client_rect = win32gui.GetClientRect(hwnd)
                    left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                    abs_x = left + ctx.get('offset_left', 0) + rel_x
                    abs_y = top + ctx.get('offset_top', 0) + rel_y

        full_img = pyautogui.screenshot()
        cropped_img = full_img.crop((abs_x, abs_y, abs_x + w, abs_y + h))
        cropped_img.save(save_path)

        # 统一复用 VisionService 写入 regions 坐标索引
        VisionService.save_region(project_path, clean_key, crop_rect)

        return {'status': 'success', 'file_path': save_path, 'key': clean_key}

    @staticmethod
    def take_screenshot(request_data: dict) -> dict:
        window_title = request_data.get('window_title')
        offset_top = request_data.get('offset_top', 0)
        offset_bottom = request_data.get('offset_bottom', 0)
        offset_left = request_data.get('offset_left', 0)
        offset_right = request_data.get('offset_right', 0)

        if window_title:
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                raise HTTPException(status_code=404, detail='未找到窗口')
            client_rect = win32gui.GetClientRect(hwnd)
            left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
            right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
            x = left + offset_left
            y = top + offset_top
            w = (right - left) - offset_left - offset_right
            h = (bottom - top) - offset_bottom - offset_bottom
            if w <= 0 or h <= 0:
                raise HTTPException(status_code=400, detail='裁剪后区域无效')
            region = (x, y, w, h)
        else:
            screen_w, screen_h = pyautogui.size()
            region = (0, 0, screen_w, screen_h)

        screenshot = pyautogui.screenshot(region=region)
        buffered = io.BytesIO()
        screenshot.save(buffered, format='PNG')
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return {'image': f'data:image/png;base64,{img_base64}', 'rect': region}
