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

        # ----- 1. 模板图片（兼容新旧结构） -----
        if "image_source" in params and isinstance(params["image_source"], str):
            template_name = params["image_source"]
        else:
            # 兼容旧数据：image_source 是字典 {"type": "file", "data": "xxx"}
            image_source = params.get("image_source", {})
            template_name = image_source.get("data", "")
            if image_source.get("type") != "file" and not template_name:
                context.log("不支持的图片源类型", "error")
                return {"success": False, "error": "unsupported image source type"}

        if not template_name:
            context.log("未指定模板图片名称", "error")
            return {"success": False, "error": "template name missing"}

        template_path = resource_path(os.path.join("templates", template_name + ".png"))
        if not os.path.exists(template_path):
            # 兼容旧数据：尝试根目录
            fallback_path = resource_path(os.path.join("templates", os.path.basename(template_name) + ".png"))
            if os.path.exists(fallback_path):
                context.log(f"模板文件在根目录找到，使用备选: {fallback_path}", "warning")
                template_path = fallback_path
            else:
                context.log(f"模板文件不存在: {template_path}", "error")
                return {"success": False, "error": "template not found"}

        try:
            template = load_image(template_path)
        except FileNotFoundError:
            context.log(f"模板文件加载失败: {template_path}", "error")
            return {"success": False, "error": "template not found"}

        # ----- 2. 搜索区域（兼容新旧结构） -----
        # 新结构：region_type, region_value, region_is_relative
        # 旧结构：region 字典
        if "region_type" in params:
            region_type = params.get("region_type", "fullwindow")
            region_value = params.get("region_value", [0, 0, 0, 0])
            region_is_relative = params.get("region_is_relative", False)
        else:
            region_conf = params.get("region", {})
            region_type = region_conf.get("type", "fullwindow")
            region_value = region_conf.get("value", [0, 0, 0, 0])
            region_is_relative = region_conf.get("is_relative", False)

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

        # ----- 3. 参数：阈值、超时、灰度 -----
        threshold = params.get("threshold", 85) / 100.0
        timeout = params.get("timeout", 3000) / 1000.0
        gray_scale = params.get("gray_scale", False)

        # ----- 4. 执行匹配 -----
        start_time = time.time()
        found = False
        pos = None
        max_val = 0.0

        while time.time() - start_time < timeout:
            screenshot = pyautogui.screenshot(region=region_rect)
            screen = np.array(screenshot)
            if gray_scale:
                screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
                template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
                result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            else:
                result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
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
                break
            time.sleep(0.1)

        if context.image_log_enabled:
            self._save_debug_screenshot(screen, template_name, context)

        # ----- 5. 处理结果 -----
        if found:
            context.log(f"匹配成功: {template_name}, 位置: {pos}, 置信度: {max_val:.2f}")

            # ----- 5a. 执行成功操作（on_success_action） -----
            # 新结构：on_success_action 是字符串 "noop" 或 "click_center"
            # 旧结构：on_success_action 是字典 {"type": "click_center", "click_count": 1, "var_name": ""}
            action = params.get("on_success_action")
            if isinstance(action, str):
                action_type = action
                click_count = 1  # 默认点击1次
                var_name = ""
            else:
                # 兼容旧数据
                action_conf = params.get("on_success_action", {})
                action_type = action_conf.get("type", "noop")
                click_count = action_conf.get("click_count", 1)
                var_name = action_conf.get("var_name", "")

            if action_type == "click_center":
                pyautogui.click(pos[0], pos[1], clicks=click_count)
            elif action_type == "assign_variable":
                if var_name:
                    context.variables[var_name] = pos

            # ----- 5b. 读取跳转配置（on_success / on_failure） -----
            # 新结构：on_success 是字典 {"type": "next", "target": "", "target_node": ""}
            # 旧结构：没有 on_success，使用默认 next
            success_jump = params.get("on_success", {})
            if success_jump:
                jump_type = success_jump.get("type", "next")
                target = success_jump.get("target", "")
                target_node = success_jump.get("target_node", "")
            else:
                # 如果不存在，使用默认跳转（next）
                jump_type = "next"
                target = ""
                target_node = ""

            return {
                "success": True,
                "pos": pos,
                "confidence": max_val,
                "jump": {"type": jump_type, "target": target, "target_node": target_node}
            }
        else:
            context.log(f"匹配超时: {template_name}, 最高置信度: {max_val:.2f}")

            # ----- 失败跳转（on_failure） -----
            failure_jump = params.get("on_failure", {})
            if failure_jump:
                jump_type = failure_jump.get("type", "next")
                target = failure_jump.get("target", "")
                target_node = failure_jump.get("target_node", "")
            else:
                jump_type = "next"
                target = ""
                target_node = ""

            return {
                "success": False,
                "timeout": True,
                "jump": {"type": jump_type, "target": target, "target_node": target_node}
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