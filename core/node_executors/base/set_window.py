# core/node_executors/base/set_window.py
import win32gui
import win32con
import subprocess
import re
import logging
import pyautogui
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.emulator_presets import get_emulator_offset

logger = logging.getLogger(__name__)


@NodeExecutorRegistry.register("set_window")
class SetWindowNodeExecutor(BaseNodeExecutor):

    def execute(self, node, context):
        params = node.params
        work_mode = params.get("work_mode", "window")

        # ---------------- 1. 全桌面模式 (Desktop Mode) ----------------
        if work_mode == "desktop":
            context.log("🖥️ 切换为 [全桌面模式]，清除窗口句柄限制")
            screen_w, screen_h = pyautogui.size()

            # 解析裁剪偏移 (支持新版 [T, B, L, R] 列表和旧版字典)
            raw_offset = params.get("content_offset", [0, 0, 0, 0])
            if isinstance(raw_offset, list) and len(raw_offset) >= 4:
                off_top, off_bottom, off_left, off_right = raw_offset[0], raw_offset[1], raw_offset[2], raw_offset[3]
            elif isinstance(raw_offset, dict):
                off_top = raw_offset.get("top", 0)
                off_bottom = raw_offset.get("bottom", 0)
                off_left = raw_offset.get("left", 0)
                off_right = raw_offset.get("right", 0)
            else:
                off_top = off_bottom = off_left = off_right = 0

            # 计算桌面裁剪后的工作坐标区
            crop_w = screen_w - off_left - off_right
            crop_h = screen_h - off_top - off_bottom

            context.window_hwnd = None
            context.window_rect = (off_left, off_top, max(1, crop_w), max(1, crop_h))
            context.is_emulator = False
            context.device_id = None
            context.android_width = None
            context.android_height = None

            context.variables.pop("window_original_rect", None)
            context.variables["window_content_offset"] = {"top": off_top, "bottom": off_bottom, "left": off_left, "right": off_right}
            context.variables["window_rect"] = context.window_rect

            context.log(f"✅ 全桌面工作区设置成功 | 区域: {context.window_rect}")
            return self.build_jump_result(True, params.get("on_success", {}))

        # ---------------- 2. 指定窗口/模拟器模式 (Window Mode) ----------------
        title = params.get("title")
        if not title:
            context.log("❌ [set_window] 缺少窗口标题参数", "error")
            return self.build_jump_result(False, params.get("on_failure", {}), error="missing title")

        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            context.log(f"⚠️ [set_window] 未找到标题为 [{title}] 的窗口", "warning")
            return self.build_jump_result(False, params.get("on_failure", {}), error=f"window not found: {title}")

        # 默认激活并置顶窗口
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            context.log(f"✅ [set_window] 窗口已自动置顶激活: {title}")
        except Exception as e:
            context.log(f"⚠️ [set_window] 激活窗口失败: {e}", "warning")

        # 读取裁剪偏移配置 (兼容列表 [T,B,L,R] 和字典)
        raw_offset = params.get("content_offset", [0, 0, 0, 0])
        if isinstance(raw_offset, list) and len(raw_offset) >= 4:
            offset_top, offset_bottom, offset_left, offset_right = raw_offset[0], raw_offset[1], raw_offset[2], raw_offset[3]
        elif isinstance(raw_offset, dict) and any(v != 0 for v in raw_offset.values()):
            offset_top = raw_offset.get("top", 0)
            offset_bottom = raw_offset.get("bottom", 0)
            offset_left = raw_offset.get("left", 0)
            offset_right = raw_offset.get("right", 0)
        else:
            if params.get("is_emulator", False):
                auto_off = get_emulator_offset(title)
                offset_top = auto_off.get("top", 0)
                offset_bottom = auto_off.get("bottom", 0)
                offset_left = auto_off.get("left", 0)
                offset_right = auto_off.get("right", 0)
                context.log(f"📱 自动匹配模拟器预设裁剪偏移: {auto_off}")
            else:
                offset_top = offset_bottom = offset_left = offset_right = 0

        # 解析目标尺寸 (兼容新版 list [W, H] 与旧版单独 width/height 字段)
        raw_size = params.get("target_content_size", [0, 0])
        if isinstance(raw_size, list) and len(raw_size) >= 2:
            target_w, target_h = raw_size[0], raw_size[1]
        else:
            target_w = params.get("target_content_width", 0)
            target_h = params.get("target_content_height", 0)

        if target_w > 0 and target_h > 0:
            context.log(f"📏 检测到目标内容尺寸: {target_w}x{target_h}，准备调整窗口大小...")
            try:
                window_rect = win32gui.GetWindowRect(hwnd)
                pos_x, pos_y = window_rect[0], window_rect[1]

                cur_client_rect = win32gui.GetClientRect(hwnd)
                cur_window_rect = win32gui.GetWindowRect(hwnd)
                border_w = (cur_window_rect[2] - cur_window_rect[0]) - cur_client_rect[2]
                border_h = (cur_window_rect[3] - cur_window_rect[1]) - cur_client_rect[3]

                client_w = target_w + offset_left + offset_right
                client_h = target_h + offset_top + offset_bottom

                outer_w = client_w + border_w
                outer_h = client_h + border_h

                win32gui.SetWindowPos(hwnd, None, pos_x, pos_y, outer_w, outer_h, win32con.SWP_NOZORDER)
                context.log(f"✅ 窗口尺寸已调整为外框: {outer_w}x{outer_h} | 内容区: {target_w}x{target_h}")
            except Exception as e:
                context.log(f"⚠️ [set_window] 调整尺寸失败: {e}", "warning")

        # 计算调整后的实际内容坐标区
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        original_rect = (left, top, right - left, bottom - top)

        new_left = left + offset_left
        new_top = top + offset_top
        new_width = original_rect[2] - offset_left - offset_right
        new_height = original_rect[3] - offset_top - offset_bottom
        content_rect = (new_left, new_top, new_width, new_height)

        # 更新全局变量
        context.window_hwnd = hwnd
        context.window_rect = content_rect
        context.variables["window_hwnd"] = hwnd
        context.variables["window_rect"] = content_rect
        context.variables["window_original_rect"] = original_rect
        context.variables["window_content_offset"] = {"top": offset_top, "bottom": offset_bottom, "left": offset_left, "right": offset_right}

        # 模拟器 ADB 检测
        is_emulator = params.get("is_emulator", False)
        context.is_emulator = is_emulator
        if is_emulator:
            device_id = self._auto_detect_device(title)
            if device_id:
                context.device_id = device_id
                android_w, android_h = self._get_android_resolution(device_id)
                if android_w and android_h:
                    context.android_width = android_w
                    context.android_height = android_h
                    context.variables["android_width"] = android_w
                    context.variables["android_height"] = android_h
                    context.log(f"🤖 [ADB] 设备: {device_id} | Android 物理分辨率: {android_w}x{android_h}")
                else:
                    context.log(f"⚠️ [ADB] 设备 {device_id} 无法获取 Android 分辨率", "warning")
            else:
                context.log("⚠️ 未找到匹配的 ADB 设备，模拟器模式将自动回退为桌面鼠标点击", "warning")
                context.is_emulator = False

        context.log(f"🎉 工作窗口设置完成 | 标题: {title} | 最终内容区域: {content_rect}")
        return self.build_jump_result(True, params.get("on_success", {}))

    # ---------- 辅助工具函数 ----------
    def _auto_detect_device(self, title):
        match = re.search(r'(\d{4,5})$', title)
        if match:
            port = match.group(1)
            candidates = [f"127.0.0.1:{port}", f"emulator-{port}"]
            for candidate in candidates:
                if self._check_device(candidate):
                    return candidate
        devices = self._get_adb_devices()
        return devices[0] if devices else None

    def _check_device(self, device_id):
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "echo", "test"],
                capture_output=True, text=True, timeout=2
            )
            return result.returncode == 0 and "test" in result.stdout
        except:
            return False

    def _get_adb_devices(self):
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if "device" in line and "offline" not in line:
                    devices.append(line.split()[0])
            return devices
        except:
            return []

    def _get_android_resolution(self, device_id):
        try:
            cmd = ["adb", "-s", device_id, "shell", "wm", "size"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None, None
        except:
            return None, None


@NodeExecutorRegistry.register("reset_window")
class ResetWindowNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        context.window_hwnd = None
        context.window_rect = None
        context.is_emulator = False
        context.device_id = None
        context.android_width = None
        context.android_height = None
        context.variables.pop("window_original_rect", None)
        context.variables.pop("window_content_offset", None)
        context.log("🔄 已切换回桌面全屏模式")
        return {"success": True}