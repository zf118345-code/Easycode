# core/node_executors/base/image_recognition.py
import time
import cv2
import numpy as np
import pyautogui
import os
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import resource_path, load_image, match_template_cv


@NodeExecutorRegistry.register("image_recognition")
class ImageRecognitionNodeExecutor(BaseNodeExecutor):
    def __init__(self):
        self.debug_dir = resource_path("debug_screenshots")
        os.makedirs(self.debug_dir, exist_ok=True)

    def execute(self, node, context):
        params = node.params

        # 1. 校验模板图片
        template_name = params.get("image_source", "")
        if not template_name:
            context.log("未指定模板图片名称", "error")
            return self.build_jump_result(False, params.get("on_failure", {}), error="template name missing")

        templates_dir = os.path.normpath(os.path.join(context.project_dir, "templates"))
        template_path = os.path.normpath(os.path.join(templates_dir, template_name + ".png"))

        if not os.path.exists(template_path):
            context.log(f"模板文件不存在: {template_path}", "error")
            return self.build_jump_result(False, params.get("on_failure", {}), error="template not found")

        try:
            template = load_image(template_path)
        except Exception:
            context.log(f"模板文件加载失败: {template_path}", "error")
            return self.build_jump_result(False, params.get("on_failure", {}), error="template load error")

        # 2. 搜索区域计算
        region_type = params.get("region_type", "fullwindow")
        region_value = params.get("region_value", [0, 0, 0, 0])
        region_is_relative = params.get("region_is_relative", False)

        if region_type in ("recorded", "custom") and len(region_value) == 4:
            x, y, w, h = region_value
            if region_is_relative and context.is_window_mode():
                wx, wy, _, _ = context.get_window_rect()
                x += wx
                y += wy
            region_rect = (x, y, w, h)
        else:
            region_rect = context.get_window_rect()

        # 3. 匹配参数
        threshold = params.get("threshold", 85) / 100.0
        timeout = params.get("timeout", 3000) / 1000.0
        gray_scale = params.get("gray_scale", False)

        start_time = time.time()
        found = False
        pos = None
        max_val = 0.0

        # 4. 循环匹配逻辑
        while time.time() - start_time < timeout:
            try:
                screenshot = pyautogui.screenshot(region=region_rect)
                max_val, center_offset = match_template_cv(screenshot, template, gray_scale=gray_scale)

                if max_val >= threshold and center_offset:
                    found = True
                    x = region_rect[0] + center_offset[0]
                    y = region_rect[1] + center_offset[1]
                    pos = (x, y)
                    break
            except Exception as e:
                context.log(f"匹配过程发生异常: {e}", "warning")
                break

            time.sleep(0.1)

        if context.image_log_enabled and 'screenshot' in locals():
            self._save_debug_screenshot(np.array(screenshot), template_name, context)

        # 5. 统一结果处理
        if found:
            context.log(f"匹配成功: {template_name}, 位置: {pos}, 置信度: {max_val:.2f}")
            if params.get("on_success_action") == "click_center":
                pyautogui.click(pos[0], pos[1], clicks=1)

            return self.build_jump_result(
                True,
                params.get("on_success", {}),
                extra={"pos": pos, "confidence": max_val}
            )
        else:
            context.log(f"匹配超时: {template_name}, 最高置信度: {max_val:.2f}")
            return self.build_jump_result(
                False,
                params.get("on_failure", {}),
                error="timeout"
            )

    def _save_debug_screenshot(self, screen, template_name, context):
        timestamp = int(time.time() * 1000)
        task_name = context.current_task_name.replace(" ", "_") if context.current_task_name else "unknown"
        node_index = context.current_node_index + 1
        safe_name = template_name.replace("/", "_").replace("\\", "_")
        filename = f"{task_name}_{node_index}_{safe_name}_{timestamp}.png"
        filepath = os.path.join(self.debug_dir, filename)

        cv2.imwrite(filepath, cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))

        # 滚动删除超出的老截图（保持最多 20 张）
        files = sorted(
            [f for f in os.listdir(self.debug_dir) if f.endswith(".png")],
            key=lambda x: os.path.getmtime(os.path.join(self.debug_dir, x))
        )
        if len(files) > 20:
            for old_file in files[:-20]:
                os.remove(os.path.join(self.debug_dir, old_file))