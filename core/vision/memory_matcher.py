# core/vision/memory_matcher.py

import numpy as np

from core.utils import match_template_cv


class MemoryTemplateMatcher:
    """
    RAM 内存级 OpenCV 识图比对引擎
    彻底脱离文件系统路径，直接对全屏 BGR 矩阵与解密在内存中的模板 BGR 矩阵进行匹配
    """

    @classmethod
    def match_in_memory(
        cls,
        screen_bgr: np.ndarray,
        template_bgr: np.ndarray,
        region_type: str = 'fullwindow',
        region_value: list = None,
    ) -> tuple[float, tuple[int, int] | None]:
        """
        对内存中的图像矩阵进行区域裁切与 OpenCV 模板匹配
        :param screen_bgr: 全屏或工作区截取的 BGR 矩阵
        :param template_bgr: 解密在内存中的模板 BGR 矩阵
        :param region_type: 匹配模式 ("fullwindow", "recorded", "custom")
        :param region_value: 区域坐标 [X, Y, W, H]
        :returns: (max_score, match_loc_point)
        """
        if screen_bgr is None or template_bgr is None:
            return 0.0, None

        tpl_h, tpl_w = template_bgr.shape[:2]
        screen_h, screen_w = screen_bgr.shape[:2]

        target_roi = screen_bgr

        # 执行智能区域裁剪与外扩 Margin 保护
        if region_type in ('recorded', 'custom') and isinstance(region_value, (list, tuple)) and len(region_value) >= 4:
            rx, ry, rw, rh = [int(v) for v in region_value[:4]]

            # 区域微小时按模板尺寸自动外扩
            if rw < tpl_w or rh < tpl_h:
                center_x = rx + rw // 2
                center_y = ry + rh // 2
                rw = max(rw, int(tpl_w * 1.3))
                rh = max(rh, int(tpl_h * 1.3))
                rx = center_x - rw // 2
                ry = center_y - rh // 2

            padding = 15
            x1 = max(0, rx - padding)
            y1 = max(0, ry - padding)
            x2 = min(screen_w, rx + rw + padding)
            y2 = min(screen_h, ry + rh + padding)

            if (x2 - x1) >= tpl_w and (y2 - y1) >= tpl_h:
                target_roi = screen_bgr[y1:y2, x1:x2]

        # 调取 OpenCV 匹配引擎（screen_bgr 是 BGR 内存矩阵，跳过通道转换）
        max_val, max_loc = match_template_cv(target_roi, template_bgr, screen_is_bgr=True)
        score = max(0.0, float(max_val)) if max_val is not None and max_val > -1.0 else 0.0

        return score, max_loc
