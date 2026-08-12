# core/utils.py
import os
import sys
import json
import cv2
import re
import numpy as np
from datetime import datetime
from typing import Any


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.normpath(os.path.join(base, relative_path))


def load_image(path):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {path}")
    return img


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def match_template_cv(screen_img, template_img, gray_scale=False):
    """
    通用 OpenCV 模板匹配函数
    返回: (max_val, max_loc_center)
    """
    screen = np.array(screen_img)
    template = np.array(template_img)

    if gray_scale:
        if len(screen.shape) == 3:
            screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
        else:
            screen_gray = screen

        if len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        else:
            template_gray = template

        res_screen = screen_gray
        res_template = template_gray
    else:
        res_screen = screen
        res_template = template

    # 检查尺寸
    if res_template.shape[0] > res_screen.shape[0] or res_template.shape[1] > res_screen.shape[1]:
        return -1.0, None

    match_res = cv2.matchTemplate(res_screen, res_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(match_res)

    h, w = res_template.shape[:2]
    center_pos = (max_loc[0] + w // 2, max_loc[1] + h // 2)

    return max_val, center_pos


def resolve_template_string(text: Any, executor_ctx=None) -> Any:
    """
    ⚡ 工业级模板变量替换引擎
    支持三大命名空间:
      - 用户全局变量: {newnum} 或 {$var.newnum}
      - 节点上下文变量: {$ctx.ocr_text} / {$ctx.click_pos}
      - 系统环境变量: {$env.current_time} / {$sys.project_path}
    """
    if not isinstance(text, str) or "{" not in text:
        return text

    pattern = r'\{([^}]+)\}'

    def replace_match(match):
        expression = match.group(1).strip()

        # 1. 系统与环境变量解析 {$env.xxx} 或 {$sys.xxx}
        if expression.startswith("$env.") or expression.startswith("$sys."):
            env_key = expression.split(".", 1)[1]
            if env_key in ("current_time", "now"):
                return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif env_key in ("time_short", "time"):
                return datetime.now().strftime("%H:%M:%S")
            elif env_key in ("date", "today"):
                return datetime.now().strftime("%Y-%m-%d")
            elif env_key == "timestamp":
                return str(int(datetime.now().timestamp() * 1000))
            elif env_key == "project_path":
                return getattr(executor_ctx, "project_dir", "") or ""
            elif env_key == "task_name":
                return getattr(executor_ctx, "current_task_name", "") or ""
            elif env_key == "node_name":
                current_node = getattr(executor_ctx, "current_node", None)
                return getattr(current_node, "node_name", "") if current_node else ""
            return match.group(0)

        # 2. 节点运行期上下文解析 {$ctx.xxx}
        elif expression.startswith("$ctx."):
            ctx_key = expression.split(".", 1)[1]
            if executor_ctx and hasattr(executor_ctx, "variables"):
                if ctx_key in executor_ctx.variables:
                    return str(executor_ctx.variables[ctx_key])
            return match.group(0)

        # 3. 用户全局变量解析 {xxx} 或 {$var.xxx}
        else:
            var_key = expression.split(".", 1)[1] if expression.startswith("$var.") else expression
            if executor_ctx and hasattr(executor_ctx, "variables"):
                if var_key in executor_ctx.variables:
                    return str(executor_ctx.variables[var_key])
            return match.group(0)

    return re.sub(pattern, replace_match, text)