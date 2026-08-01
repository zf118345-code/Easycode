# core/node_executors/base/image_recognition.py
import time
import cv2
import numpy as np
import pyautogui
import os
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import resource_path, load_image

@NodeExecutorRegistry.register("image_recognition")
class ImageRecognitionNodeExecutor(BaseNodeExecutor):
    def __init__(self):
        self.debug_dir = resource_path("debug_screenshots")
        os.makedirs(self.debug_dir, exist_ok=True)

    def execute(self, node, context):
        params = node.params

        # ===== 1. 模板图片 =====
        template_name = params.get("image_source", "")
        if not template_name:
            context.log("未指定模板图片名称", "error")
            return {"success": False, "error": "template name missing"}

        templates_dir = os.path.normpath(os.path.join(context.project_dir, "templates"))
        template_path = os.path.normpath(os.path.join(templates_dir, template_name + ".png"))

        if not os.path.exists(template_path):
            context.log(f"模板文件不存在: {template_path}", "error")
            return {"success": False, "error": "template not found"}

        try:
            template = load_image(template_path)
        except FileNotFoundError:
            context.log(f"模板文件加载失败: {template_path}", "error")
            return {"success": False, "error": "template not found"}

        # ===== 2. 搜索区域 =====
        region_type = params.get("region_type", "fullwindow")
        region_value = params.get("region_value", [0, 0, 0, 0])
        region_is_relative = params.get("region_is_relative", False)

        if region_type == "fullwindow":
            region_rect = context.get_window_rect()
        elif region_type in ("recorded", "custom"):
            rect = region_value
            if rect and len(rect) == 4:
                x, y, w, h = rect
                if region_is_relative and context.is_window_mode():
                    wx, wy, _, _ = context.get_window_rect()
                    x += wx
                    y += wy
                region_rect = (x, y, w, h)
            else:
                region_rect = context.get_window_rect()
        else:
            region_rect = context.get_window_rect()

        # ===== 3. 参数：阈值、超时、灰度 =====
        threshold = params.get("threshold", 85) / 100.0
        timeout = params.get("timeout", 3000) / 1000.0
        gray_scale = params.get("gray_scale", False)

        # ===== 4. 执行匹配 =====
        start_time = time.time()
        found = False
        pos = None
        max_val = 0.0
        attempt = 0

        print("\n" + "=" * 60)
        print("【图像识别调试】")
        print(f"模板名称: {template_name}")
        print(f"模板尺寸: {template.shape if template is not None else 'None'}")
        print(f"搜索区域 (region_rect): {region_rect}")
        print(f"窗口区域 (context.get_window_rect()): {context.get_window_rect()}")
        print(f"阈值 (threshold): {threshold:.2f}")
        print(f"超时时间 (timeout): {timeout} 秒")
        print(f"灰度匹配: {gray_scale}")
        print("=" * 60)

        while time.time() - start_time < timeout:
            attempt += 1
            try:
                screenshot = pyautogui.screenshot(region=region_rect)
                screen = np.array(screenshot)

                if gray_scale:
                    screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
                    template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
                    result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
                else:
                    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)

                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                print(f"第 {attempt} 次匹配，分数: {max_val:.4f}")

                if max_val >= threshold:
                    found = True
                    h, w = template.shape[:2]
                    if region_rect:
                        x = region_rect[0] + max_loc[0] + w // 2
                        y = region_rect[1] + max_loc[1] + h // 2
                    else:
                        x = max_loc[0] + w // 2
                        y = max_loc[1] + h // 2
                    pos = (x, y)
                    print(f">>> 匹配成功！分数: {max_val:.4f}，位置: {pos}")
                    break
            except Exception as e:
                print(f"匹配异常: {e}")
                break

            time.sleep(0.1)

        if found:
            print(f"最终结果: 匹配成功，最高分数: {max_val:.4f}，位置: {pos}")
        else:
            print(f"最终结果: 匹配失败，最高分数: {max_val:.4f}，尝试次数: {attempt}")
        print("=" * 60 + "\n")

        if context.image_log_enabled:
            self._save_debug_screenshot(screen, template_name, context)

        # ===== 5. 处理结果 =====
        if found:
            context.log(f"匹配成功: {template_name}, 位置: {pos}, 置信度: {max_val:.2f}")

            # 成功操作
            action = params.get("on_success_action", "noop")
            if action == "click_center":
                pyautogui.click(pos[0], pos[1], clicks=1)

            # 成功跳转
            success_jump = params.get("on_success", {})
            jump_type = success_jump.get("jump_type", "next")
            target_task = success_jump.get("target_task", "")
            target_node = success_jump.get("target_node", "")

            return {
                "success": True,
                "pos": pos,
                "confidence": max_val,
                "jump": {
                    "type": jump_type,
                    "target": target_task,
                    "target_node": target_node
                }
            }

        else:
            context.log(f"匹配超时: {template_name}, 最高置信度: {max_val:.2f}")

            # 失败跳转
            failure_jump = params.get("on_failure", {})
            jump_type = failure_jump.get("jump_type", "next")
            target_task = failure_jump.get("target_task", "")
            target_node = failure_jump.get("target_node", "")

            return {
                "success": False,
                "timeout": True,
                "jump": {
                    "type": jump_type,
                    "target": target_task,
                    "target_node": target_node
                }
            }

    def _save_debug_screenshot(self, screen, template_name, context):
        timestamp = int(time.time() * 1000)
        task_name = context.current_task_name.replace(" ", "_") if context.current_task_name else "unknown"
        node_index = context.current_node_index + 1
        safe_name = template_name.replace("/", "_").replace("\\", "_")
        filename = f"{task_name}_{node_index}_{safe_name}_{timestamp}.png"
        filepath = os.path.join(self.debug_dir, filename)
        cv2.imwrite(filepath, cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))
        context.log(f"调试截图已保存: {filepath}")

        files = sorted(
            [f for f in os.listdir(self.debug_dir) if f.endswith(".png")],
            key=lambda x: os.path.getmtime(os.path.join(self.debug_dir, x))
        )
        if len(files) > 20:
            for old_file in files[:-20]:
                os.remove(os.path.join(self.debug_dir, old_file))