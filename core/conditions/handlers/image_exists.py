# core/conditions/handlers/image_exists.py
import os
import cv2
import pyautogui
import numpy as np
from typing import Any
from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import match_template_cv


@ConditionRegistry.register("image_exists")
class ImageExistsEvaluator(BaseConditionEvaluator):

    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        image_source = str(params.get("image_source", "")).strip()

        # 1. 规范化 exist_mode / operator
        raw_mode = str(params.get("exist_mode") or params.get("operator", "exists")).lower()
        is_not_exists_mode = raw_mode in ("not_exists", "not_exist", "not_found")

        # 2. 规范化 threshold 阈值 (百分比自动除以 100)
        try:
            threshold = float(params.get("threshold", 0.8))
            if threshold > 1.0:
                threshold = threshold / 100.0
        except (ValueError, TypeError):
            threshold = 0.8

        project_dir = getattr(context, 'project_dir', None) or getattr(context, 'project_path', None)

        if not image_source or not project_dir:
            if hasattr(context, "last_match_score"):
                context.last_match_score = 0.0
            return True if is_not_exists_mode else False

        clean_name = image_source.replace("\\", "/")
        if clean_name.lower().endswith(".png"):
            clean_name = clean_name[:-4]

        template_path = os.path.join(project_dir, "templates", f"{clean_name}.png")

        if not os.path.exists(template_path):
            if hasattr(context, "last_match_score"):
                context.last_match_score = 0.0
            if hasattr(context, 'log'):
                context.log(f"⚠️ [识图条件] 模板文件不存在: {template_path}", "warning")
            return True if is_not_exists_mode else False

        try:
            # 截取全屏图像 (BGR 格式)
            screen = pyautogui.screenshot()
            screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
            template_bgr = cv2.imread(template_path)

            if template_bgr is None:
                if hasattr(context, "last_match_score"):
                    context.last_match_score = 0.0
                return True if is_not_exists_mode else False

            tpl_h, tpl_w = template_bgr.shape[:2]
            screen_h, screen_w = screen_bgr.shape[:2]

            # 3. 提取匹配区域参数 (多键名兼容)
            region_type = str(params.get("region_type") or params.get("match_mode", "fullwindow")).lower()
            region_value = (
                params.get("region_value") or
                params.get("crop_rect") or
                params.get("region") or
                [0, 0, 0, 0]
            )

            target_roi = screen_bgr

            # ⚡ 4. 智能区域裁剪与外扩 Margin 保护
            if region_type in ("recorded", "custom") and isinstance(region_value, (list, tuple)) and len(region_value) >= 4:
                rx, ry, rw, rh = [int(v) for v in region_value[:4]]

                # 如果录制区域过于微小（低于模板尺寸），自动以原区域中心点强行按模板尺寸外扩 20%
                if rw < tpl_w or rh < tpl_h:
                    center_x = rx + rw // 2
                    center_y = ry + rh // 2
                    rw = max(rw, int(tpl_w * 1.3))
                    rh = max(rh, int(tpl_h * 1.3))
                    rx = center_x - rw // 2
                    ry = center_y - rh // 2

                # 向四周额外外扩 15 像素，容忍轻微移动偏差
                padding = 15
                x1 = max(0, rx - padding)
                y1 = max(0, ry - padding)
                x2 = min(screen_w, rx + rw + padding)
                y2 = min(screen_h, ry + rh + padding)

                # 确保裁剪出的 ROI 高度宽度都合法
                if (x2 - x1) >= tpl_w and (y2 - y1) >= tpl_h:
                    target_roi = screen_bgr[y1:y2, x1:x2]

            # ⚡ 5. 真实计算 OpenCV 匹配分数，无论高低百分之百挂载
            max_val, _ = match_template_cv(target_roi, template_bgr)
            score = max(0.0, float(max_val)) if max_val is not None and max_val > -1.0 else 0.0

            # 强制将真实的得分回传至 context
            if hasattr(context, "last_match_score"):
                context.last_match_score = score

            found = score >= threshold
        except Exception as e:
            score = 0.0
            if hasattr(context, "last_match_score"):
                context.last_match_score = 0.0
            found = False

        return not found if is_not_exists_mode else found