# core/node_executors/base/click.py
import pyautogui
import subprocess
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor


@NodeExecutorRegistry.register("click")
class ClickNodeExecutor(BaseNodeExecutor):

    def execute(self, node, context):
        params = node.params

        pos = params.get("position", [0, 0])
        if isinstance(pos, list) and len(pos) >= 2:
            x, y = pos[0], pos[1]
        elif isinstance(pos, dict):
            x, y = pos.get("x", 0), pos.get("y", 0)
        else:
            x, y = 0, 0

        wx, wy = 0, 0
        if context.is_window_mode():
            win_rect = context.get_window_rect()
            wx, wy = win_rect[0], win_rect[1]

        # 模拟器模式 (ADB 后台静默点击)
        if context.is_emulator and context.device_id:
            if context.android_width and context.android_height:
                win_rect = context.get_window_rect()
                win_w, win_h = win_rect[2], win_rect[3]

                # ⭐ 动态横竖屏方向校正算法
                raw_a_w, raw_a_h = context.android_width, context.android_height
                if win_w > win_h:  # PC 窗口为横屏
                    real_a_w = max(raw_a_w, raw_a_h)
                    real_a_h = min(raw_a_w, raw_a_h)
                else:  # PC 窗口为竖屏
                    real_a_w = min(raw_a_w, raw_a_h)
                    real_a_h = max(raw_a_w, raw_a_h)

                # 映射到 Android 动态校正后的物理坐标
                android_x = int((x / win_w) * real_a_w)
                android_y = int((y / win_h) * real_a_h)

                context.log(
                    f"📱 ADB 静默点击 [横竖屏已矫正]: 窗口相对({x},{y}) -> Android物理({android_x},{android_y}) | 当前画幅:{real_a_w}x{real_a_h}")
                return self._adb_click(context.device_id, android_x, android_y, context)
            else:
                context.log("⚠️ Android 分辨率未获取，回退为 PC 物理点击", "warning")
                pyautogui.click(wx + x, wy + y)
                return {"success": True}
        else:
            # PC 模式 (物理移动鼠标)
            context.log(f"🖱️ PC 物理鼠标点击: 屏幕绝对坐标({wx + x}, {wy + y})")
            pyautogui.click(wx + x, wy + y)
            return {"success": True}

    def _adb_click(self, device_id, x, y, context):
        try:
            cmd = ["adb", "-s", device_id, "shell", "input", "tap", str(x), str(y)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                context.log(f"❌ ADB 点击指令失败: {result.stderr}", "error")
                return {"success": False}
            return {"success": True}
        except Exception as e:
            context.log(f"❌ ADB 点击触发异常: {e}", "error")
            return {"success": False}