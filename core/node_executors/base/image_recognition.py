# core/node_executors/base/image_recognition.py
import os
import subprocess
import time

import cv2
import numpy as np
import pyautogui
from core.services import screenshot_service

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.utils import load_image, match_template_cv, resource_path


@NodeExecutorRegistry.register('image_recognition')
class ImageRecognitionNodeExecutor(BaseNodeExecutor):
    def __init__(self):
        self.debug_dir = resource_path('debug_screenshots')
        os.makedirs(self.debug_dir, exist_ok=True)

    def execute(self, node, context):
        params = node.params

        # 1. 校验模板图片
        template_name = params.get('image_source', '')
        if not template_name:
            context.log('❌ 未指定模板图片名称', 'error')
            return self.build_jump_result(False, params.get('on_failure', {}), error='template name missing')

        # ⚡ 工业级优化：优先从内存密包解密出的 _memory_templates 中直接获取矩阵，实现零落盘
        memory_templates = getattr(context, '_memory_templates', {})
        template = None
        if memory_templates and template_name in memory_templates:
            template = memory_templates[template_name]
            context.log(f'📦 [内存加载] 成功从密包 RAM 中获取模板: {template_name}')
        else:
            # 降级：若内存中没有（在 Studio IDE 调试时），则去物理磁盘读取
            templates_dir = os.path.normpath(os.path.join(context.project_dir, 'templates'))
            template_path = os.path.normpath(os.path.join(templates_dir, template_name + '.png'))

            if not os.path.exists(template_path):
                context.log(f'❌ 模板文件不存在: {template_path}', 'error')
                return self.build_jump_result(False, params.get('on_failure', {}), error='template not found')

            try:
                template = load_image(template_path)
            except Exception:
                context.log(f'❌ 模板文件加载失败: {template_path}', 'error')
                return self.build_jump_result(False, params.get('on_failure', {}), error='template load error')

        # 2. 搜索区域计算
        region_type = params.get('region_type', 'fullwindow')
        region_value = params.get('region_value', [0, 0, 0, 0])
        region_is_relative = params.get('region_is_relative', False)

        if region_type in ('recorded', 'custom') and len(region_value) == 4:
            x, y, w, h = region_value
            if region_is_relative and context.is_window_mode():
                wx, wy, _, _ = context.get_window_rect()
                x += wx
                y += wy
            region_rect = (x, y, w, h)
        else:
            region_rect = context.get_window_rect()

        # 3. 匹配参数
        threshold = params.get('threshold', 85) / 100.0
        timeout = params.get('timeout', 3000) / 1000.0
        gray_scale = params.get('gray_scale', False)

        start_time = time.time()
        found = False
        pos = None  # 绝对屏幕坐标 (x, y)
        rel_pos = None
        max_val = 0.0

        # 4. 循环匹配逻辑
        while time.time() - start_time < timeout:
            try:
                screenshot = screenshot_service.capture(region=region_rect)
                max_val, center_offset = match_template_cv(screenshot, template, gray_scale=gray_scale)

                if max_val >= threshold and center_offset:
                    found = True
                    rel_pos = center_offset
                    x = region_rect[0] + center_offset[0]
                    y = region_rect[1] + center_offset[1]
                    pos = (x, y)
                    break
            except Exception as e:
                context.log(f'⚠️ 匹配过程发生异常: {e}', 'warning')
                break

            time.sleep(0.1)

        if context.image_log_enabled and 'screenshot' in locals():
            self._save_debug_screenshot(np.array(screenshot), template_name, context)

        # 5. 统一结果与自动智能点击处理
        if found:
            context.log(f'🎯 匹配成功: [{template_name}] | 置信度: {max_val:.2f} | 位置: {pos}')

            if params.get('on_success_action') == 'click_center':
                self._smart_click(pos, context)

            return self.build_jump_result(True, params.get('on_success', {}), extra={'pos': pos, 'confidence': max_val})
        else:
            context.log(f'⏰ 匹配超时: [{template_name}] | 最高置信度: {max_val:.2f} (未达到 {threshold:.2f})')
            return self.build_jump_result(False, params.get('on_failure', {}), error='timeout')

    def _smart_click(self, abs_pos, context):
        """智能点击分发：包含动态横竖屏方向矫正映射"""
        if context.is_emulator and context.device_id:
            if context.android_width and context.android_height:
                win_rect = context.get_window_rect()
                win_w, win_h = win_rect[2], win_rect[3]

                # 识别到的中心点相对于工作窗口客户区的 (x, y)
                crop_x = abs_pos[0] - win_rect[0]
                crop_y = abs_pos[1] - win_rect[1]

                # ⭐ 动态横竖屏方向校正算法
                raw_a_w, raw_a_h = context.android_width, context.android_height
                if win_w > win_h:  # 横屏
                    real_a_w = max(raw_a_w, raw_a_h)
                    real_a_h = min(raw_a_w, raw_a_h)
                else:  # 竖屏
                    real_a_w = min(raw_a_w, raw_a_h)
                    real_a_h = max(raw_a_w, raw_a_h)

                # 映射到 Android 的实际物理像素
                android_x = int((crop_x / win_w) * real_a_w)
                android_y = int((crop_y / win_h) * real_a_h)

                context.log(
                    f'📱 图像识别 [ADB静默点击(已矫正)]: 窗口相对({crop_x},{crop_y}) -> Android物理({android_x},{android_y}) | 画幅:{real_a_w}x{real_a_h}'
                )
                try:
                    cmd = ['adb', '-s', context.device_id, 'shell', 'input', 'tap', str(android_x), str(android_y)]
                    subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                except Exception as e:
                    context.log(f'❌ ADB 点击异常: {e}', 'error')
            else:
                context.log('⚠️ 未获取到 Android 分辨率，回退为 PC 物理点击', 'warning')
                self._pc_click(abs_pos[0], abs_pos[1], context)
        else:
            self._pc_click(abs_pos[0], abs_pos[1], context)

    @staticmethod
    def _pc_click(screen_x, screen_y, context):
        """PC 点击：绑定窗口时后台投递（多开友好），否则物理鼠标"""
        hwnd = getattr(context, 'window_hwnd', None)
        if hwnd:
            from core.services.background_input import background_click

            result = background_click(hwnd, screen_x, screen_y)
            context.log(
                f'🖱️ 图像识别 [后台点击窗口(#{hwnd})]: 屏幕坐标({screen_x}, {screen_y})'
                + ('' if result.get('ok') else f' ❌ {result.get("message", "")}')
            )
        else:
            context.log(f'🖱️ 图像识别 [PC物理点击]: 屏幕绝对坐标({screen_x}, {screen_y})')
            pyautogui.click(screen_x, screen_y, clicks=1)

    def _save_debug_screenshot(self, screen, template_name, context):
        timestamp = int(time.time() * 1000)
        task_name = context.current_task_name.replace(' ', '_') if context.current_task_name else 'unknown'
        node_index = context.current_node_index + 1
        safe_name = template_name.replace('/', '_').replace('\\', '_')
        filename = f'{task_name}_{node_index}_{safe_name}_{timestamp}.png'
        filepath = os.path.join(self.debug_dir, filename)

        cv2.imwrite(filepath, cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))

        files = sorted(
            [f for f in os.listdir(self.debug_dir) if f.endswith('.png')],
            key=lambda x: os.path.getmtime(os.path.join(self.debug_dir, x)),
        )
        if len(files) > 20:
            for old_file in files[:-20]:
                os.remove(os.path.join(self.debug_dir, old_file))
