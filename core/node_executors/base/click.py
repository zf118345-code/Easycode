# core/node_executors/click.py
import time
import pyautogui
import subprocess
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor

@NodeExecutorRegistry.register("click")
class ClickNodeExecutor(BaseNodeExecutor):

    def execute(self, node, context):
        params = node.params

        # 从 position 数组读取坐标
        pos = params.get("position", [0, 0])
        if isinstance(pos, list) and len(pos) >= 2:
            x = pos[0]
            y = pos[1]
        else:
            # 兼容旧数据（如果是字典回退）
            if isinstance(pos, dict):
                x = pos.get("x", 0)
                y = pos.get("y", 0)
            else:
                x = 0
                y = 0

        # 窗口偏移
        wx, wy = 0, 0
        if context.is_window_mode():
            win_rect = context.get_window_rect()
            wx, wy = win_rect[0], win_rect[1]

        # 模拟器处理
        if context.is_emulator and context.device_id:
            if context.android_width and context.android_height:
                win_rect = context.get_window_rect()
                win_w, win_h = win_rect[2], win_rect[3]
                android_x = int((x / win_w) * context.android_width)
                android_y = int((y / win_h) * context.android_height)
                context.log(f"ADB 点击: 窗口坐标({x},{y}) -> Android({android_x},{android_y})")
                return self._adb_click(context.device_id, android_x, android_y, context)
            else:
                context.log("Android 分辨率未设置，回退到 PC 点击", "warning")
                pyautogui.click(wx + x, wy + y)
                return {"success": True}
        else:
            context.log(f"PC 点击: ({wx + x}, {wy + y})")
            pyautogui.click(wx + x, wy + y)
            return {"success": True}

    def _adb_click(self, device_id, x, y, context):
        try:
            cmd = ["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                context.log(f"ADB 点击失败: {result.stderr}", "error")
                return {"success": False}
            return {"success": True}
        except Exception as e:
            context.log(f"ADB 点击异常: {e}", "error")
            return {"success": False}