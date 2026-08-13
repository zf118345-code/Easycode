# core/conditions/handlers/image_exists.py
import os
import cv2
import pyautogui
import numpy as np
from typing import Any
from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.vision.memory_matcher import MemoryTemplateMatcher


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

        if not image_source:
            if hasattr(context, "last_match_score"):
                context.last_match_score = 0.0
            return True if is_not_exists_mode else False

        clean_name = image_source.replace("\\", "/")
        if clean_name.lower().endswith(".png"):
            clean_name = clean_name[:-4]

        # ⚡ 3. 核心升级：内存与磁盘双通道模板读取 (支持 DRM 零落盘加密模式)
        template_bgr = None

        # 通道 A: 尝试从 RAM 内存对象中提取已解密的模板矩阵
        memory_templates = getattr(context, 'memory_templates', None)
        if isinstance(memory_templates, dict) and clean_name in memory_templates:
            template_bgr = memory_templates[clean_name]

        # 通道 B: 内存未命中时，降级从磁盘模板目录读取 (Studio IDE 调试模式)
        if template_bgr is None and project_dir:
            template_path = os.path.join(project_dir, "templates", f"{clean_name}.png")
            if os.path.exists(template_path):
                template_bgr = cv2.imread(template_path)

        if template_bgr is None:
            if hasattr(context, "last_match_score"):
                context.last_match_score = 0.0
            if hasattr(context, 'log'):
                context.log(f"⚠️ [识图条件] 无法获取模板矩阵 (内存与磁盘均未命中): {clean_name}", "warning")
            return True if is_not_exists_mode else False

        try:
            # 4. 截取全屏图像 (BGR 格式)
            screen = pyautogui.screenshot()
            screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

            # 5. 提取匹配区域参数
            region_type = str(params.get("region_type") or params.get("match_mode", "fullwindow")).lower()
            region_value = (
                    params.get("region_value") or
                    params.get("crop_rect") or
                    params.get("region") or
                    [0, 0, 0, 0]
            )

            # ⚡ 6. 调取 MemoryTemplateMatcher 内存级比对引擎
            score, _ = MemoryTemplateMatcher.match_in_memory(
                screen_bgr=screen_bgr,
                template_bgr=template_bgr,
                region_type=region_type,
                region_value=region_value
            )

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