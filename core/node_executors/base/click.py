# core/node_executors/base/click.py
import subprocess

import pyautogui

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.background_input import background_click


@NodeExecutorRegistry.register('click')
class ClickNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params

        pos = params.get('position', [0, 0])
        if isinstance(pos, list) and len(pos) >= 2:
            x, y = pos[0], pos[1]
        elif isinstance(pos, dict):
            x, y = pos.get('x', 0), pos.get('y', 0)
        else:
            x, y = 0, 0

        # 坐标 (0,0) 视为未设置：避免误点屏幕左上角（旧默认值）导致点错/报错
        if x == 0 and y == 0:
            context.log('⚠️ 点击位置未设置（坐标为 0,0），已跳过点击，请先在表单中设置点击位置', 'warning')
            return self.build_jump_result(False, params.get('on_success', {}))

        wx, wy = 0, 0
        if context.is_window_mode():
            win_rect = context.get_window_rect()
            wx, wy = win_rect[0], win_rect[1]

        success = True
        # 模拟器模式 (ADB 后台静默点击)
        if context.is_emulator and context.device_id:
            if context.android_width and context.android_height:
                win_rect = context.get_window_rect()
                win_w, win_h = win_rect[2], win_rect[3]

                raw_a_w, raw_a_h = context.android_width, context.android_height
                if win_w > win_h:
                    real_a_w = max(raw_a_w, raw_a_h)
                    real_a_h = min(raw_a_w, raw_a_h)
                else:
                    real_a_w = min(raw_a_w, raw_a_h)
                    real_a_h = max(raw_a_w, raw_a_h)

                android_x = int((x / win_w) * real_a_w)
                android_y = int((y / win_h) * real_a_h)

                context.log(
                    f'📱 ADB 静默点击 [横竖屏已矫正]: 窗口相对({x},{y}) -> Android物理({android_x},{android_y})'
                )
                res = self._adb_click(context.device_id, android_x, android_y, context)
                success = res.get('success', True)
            else:
                context.log('⚠️ Android 分辨率未获取，回退为 PC 物理点击', 'warning')
                pyautogui.click(wx + x, wy + y)
        else:
            hwnd = getattr(context, 'window_hwnd', None)
            if hwnd:
                # ⚡ 多开友好：向绑定窗口投递后台点击，不占用物理鼠标
                result = background_click(hwnd, wx + x, wy + y)
                success = result.get('ok', False)
                context.log(
                    f'🖱️ 后台点击窗口(#{hwnd}): 屏幕坐标({wx + x}, {wy + y})'
                    + ('' if success else f' ❌ {result.get("message", "")}')
                )
            else:
                context.log(f'🖱️ PC 物理鼠标点击: 屏幕绝对坐标({wx + x}, {wy + y})')
                pyautogui.click(wx + x, wy + y)

        # ⭐ 支持通过 on_success 灵活控制跳转
        return self.build_jump_result(success, params.get('on_success', {}))

    def _adb_click(self, device_id, x, y, context):
        try:
            cmd = ['adb', '-s', device_id, 'shell', 'input', 'tap', str(x), str(y)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                context.log(f'❌ ADB 点击指令失败: {result.stderr}', 'error')
                return {'success': False}
            return {'success': True}
        except Exception as e:
            context.log(f'❌ ADB 点击触发异常: {e}', 'error')
            return {'success': False}
