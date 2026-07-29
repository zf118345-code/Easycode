# core/node_executors/set_window.py
import win32gui
import win32con
import subprocess
import re
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.emulator_presets import get_emulator_offset

@NodeExecutorRegistry.register("set_window")
class SetWindowNodeExecutor(BaseNodeExecutor):

    def execute(self, node, context):
        params = node.params
        title = params.get("title")
        if not title:
            context.log("set_window 缺少 title 参数", "error")
            return {"success": False, "error": "missing title"}

        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            context.log(f"未找到窗口: {title}", "warning")
            return {"success": False, "error": f"window not found: {title}"}

        if params.get("activate", True):
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                context.log(f"窗口已激活: {title}")
            except Exception as e:
                context.log(f"激活窗口失败: {e}", "warning")

        # 获取原始客户区
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        original_rect = (left, top, right-left, bottom-top)

        # 获取内容偏移（用户配置或预设）
        content_offset = params.get("content_offset")
        if not content_offset or all(v == 0 for v in content_offset.values()):
            if params.get("is_emulator", False):
                content_offset = get_emulator_offset(title)
                context.log(f"自动应用模拟器预设偏移: {content_offset}")
            else:
                content_offset = {"top": 0, "bottom": 0, "left": 0, "right": 0}
        else:
            for k in ["top", "bottom", "left", "right"]:
                content_offset.setdefault(k, 0)

        # 计算内容区域
        new_left = left + content_offset["left"]
        new_top = top + content_offset["top"]
        new_width = original_rect[2] - content_offset["left"] - content_offset["right"]
        new_height = original_rect[3] - content_offset["top"] - content_offset["bottom"]
        content_rect = (new_left, new_top, new_width, new_height)

        # === 关键：更新上下文 ===
        context.window_hwnd = hwnd
        context.window_rect = content_rect          # 后续操作使用此区域
        context.variables["window_hwnd"] = hwnd
        context.variables["window_rect"] = content_rect
        context.variables["window_original_rect"] = original_rect
        context.variables["window_content_offset"] = content_offset

        # 模拟器模式
        is_emulator = params.get("is_emulator", False)
        context.is_emulator = is_emulator
        if is_emulator:
            device_id = params.get("device_id")
            if not device_id:
                device_id = self._auto_detect_device(title)
            if device_id:
                context.device_id = device_id
                android_w, android_h = self._get_android_resolution(device_id)
                if android_w and android_h:
                    override_w = params.get("android_width")
                    override_h = params.get("android_height")
                    if override_w and override_h:
                        android_w, android_h = override_w, override_h
                    context.android_width = android_w
                    context.android_height = android_h
                    context.variables["android_width"] = android_w
                    context.variables["android_height"] = android_h
                    context.log(f"Android 分辨率: {android_w}x{android_h}")
                else:
                    context.log("无法获取 Android 分辨率", "warning")
            else:
                context.log("未找到 ADB 设备，模拟器模式回退 PC 点击", "warning")
                context.is_emulator = False

        context.log(f"窗口已设置: {title}, 内容区域: {content_rect}, 模拟器: {is_emulator}")
        return {"success": True}

    # 辅助方法保持不变
    def _auto_detect_device(self, title):
        import re
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
            result = subprocess.run(["adb", "-s", device_id, "shell", "echo", "test"],
                                    capture_output=True, text=True, timeout=2)
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

# 保留 reset_window 和 resize_window
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
        context.log("已切换回桌面全屏模式")
        return {"success": True}

@NodeExecutorRegistry.register("resize_window")
class ResizeWindowNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        if context.window_hwnd is None:
            context.log("未设置窗口，无法调整大小", "error")
            return {"success": False, "error": "no window set"}
        params = node.params
        target_w = params.get("target_content_width")
        target_h = params.get("target_content_height")
        if not target_w or not target_h:
            context.log("resize_window 需要 target_content_width 和 target_content_height", "error")
            return {"success": False, "error": "missing target dimensions"}
        hwnd = context.window_hwnd
        original_rect = context.variables.get("window_original_rect")
        content_offset = context.variables.get("window_content_offset", {})
        if not original_rect:
            client_rect = win32gui.GetClientRect(hwnd)
            left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
            right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
            original_rect = (left, top, right-left, bottom-top)
            context.variables["window_original_rect"] = original_rect
        offset_left = content_offset.get("left", 0)
        offset_right = content_offset.get("right", 0)
        offset_top = content_offset.get("top", 0)
        offset_bottom = content_offset.get("bottom", 0)
        client_w = target_w + offset_left + offset_right
        client_h = target_h + offset_top + offset_bottom
        window_rect = win32gui.GetWindowRect(hwnd)
        pos_x, pos_y = window_rect[0], window_rect[1]
        cur_client_rect = win32gui.GetClientRect(hwnd)
        cur_window_rect = win32gui.GetWindowRect(hwnd)
        border_w = (cur_window_rect[2] - cur_window_rect[0]) - cur_client_rect[2]
        border_h = (cur_window_rect[3] - cur_window_rect[1]) - cur_client_rect[3]
        outer_w = client_w + border_w
        outer_h = client_h + border_h
        try:
            win32gui.SetWindowPos(hwnd, None, pos_x, pos_y, outer_w, outer_h, win32con.SWP_NOZORDER)
            new_client_rect = win32gui.GetClientRect(hwnd)
            if abs(new_client_rect[2] - client_w) > 3 or abs(new_client_rect[3] - client_h) > 3:
                context.log(f"调整窗口失败，目标客户区 {client_w}x{client_h}，实际 {new_client_rect[2]}x{new_client_rect[3]}", "warning")
                return {"success": False, "error": "resize verification failed"}
            context.log(f"窗口已调整: 客户区 {client_w}x{client_h}，内容区 {target_w}x{target_h}")
            return {"success": True}
        except Exception as e:
            context.log(f"调整窗口异常: {e}", "error")
            return {"success": False, "error": str(e)}