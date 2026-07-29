# core/node_executors/base/branch.py
import cv2
import numpy as np
import pyautogui
import os
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import load_image, resource_path


@NodeExecutorRegistry.register("branch")
class BranchNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        candidates = params.get("candidates", [])
        if not candidates:
            context.log("branch 节点缺少 candidates 参数", "error")
            return {"success": False, "error": "no candidates"}

        region_conf = params.get("region", {})
        if region_conf.get("type") == "recorded":
            rect = region_conf.get("value")
            if rect and len(rect) == 4:
                region = tuple(rect)
            else:
                region = context.get_window_rect()
        else:
            region = context.get_window_rect()

        default_threshold = params.get("threshold", 85) / 100.0

        best_score = -1
        best_target = None
        best_template = None

        for cand in candidates:
            template_name = cand.get("template")
            if not template_name:
                continue
            # 候选自己的阈值，否则使用节点参数的默认阈值
            threshold = cand.get("threshold", default_threshold)
            if isinstance(threshold, int):
                threshold = threshold / 100.0
            template_path = resource_path(os.path.join("templates", template_name + ".png"))
            if not os.path.exists(template_path):
                context.log(f"模板不存在: {template_path}", "warning")
                continue
            try:
                template = load_image(template_path)
            except:
                continue

            screenshot = pyautogui.screenshot(region=region)
            screen = np.array(screenshot)
            if len(screen.shape) == 3:
                screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
            else:
                screen_gray = screen
            if len(template.shape) == 3:
                template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
            else:
                template_gray = template

            if template_gray.shape[0] > screen_gray.shape[0] or template_gray.shape[1] > screen_gray.shape[1]:
                context.log(f"模板 {template_name} 大于截图区域，跳过", "warning")
                continue
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            context.log(f"模板 {template_name} 匹配分数: {max_val:.3f}")
            if max_val > best_score:
                best_score = max_val
                best_target = cand.get("target")
                best_template = template_name

        if best_score < default_threshold:
            context.log(f"最佳分数 {best_score:.3f} 低于阈值 {default_threshold}，跳转 on_failure")
            return {"success": False, "jump": {"type": "next"}}

        if best_target is None:
            context.log("未找到有效候选", "error")
            return {"success": False}

        context.log(f"选择模板 {best_template}，分数 {best_score:.3f}，跳转到 {best_target}")
        return {"success": True, "jump": {"type": "node", "target": best_target}}