# core/utils.py
import json
import os
import re
import sys
from datetime import datetime
from typing import Any

import cv2
import numpy as np


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.abspath('.')
    return os.path.normpath(os.path.join(base, relative_path))


def load_image(path):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f'Image not found: {path}')
    return img


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def match_template_cv(screen_img, template_img, gray_scale=False, screen_is_bgr=False):
    """
    通用 OpenCV 模板匹配函数（多尺度金字塔 + 通道统一）
    返回: (max_val, max_loc_center)

    ⚡ 通道统一：pyautogui 截图是 RGB（Pillow）、模板是 BGR（cv2.imread）——
    默认把截图转 BGR 与模板对齐（screen_is_bgr=False）；
    内存矩阵调用方（screen 已是 BGR）传 screen_is_bgr=True 跳过转换。
    ⚡ 多尺度：缩放级别越多越慢，默认 3 级（1.0/0.75/0.5）覆盖常见 DPI 缩放。
    """
    # 截图来自 Pillow（RGB）→ 转 BGR；模板保持 BGR（cv2.imread 约定，不再转）
    screen = np.array(screen_img)
    template = np.array(template_img)
    if not screen_is_bgr and len(screen.shape) == 3 and screen.shape[2] == 3:
        screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

    if gray_scale:
        if len(screen.shape) == 3:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        if len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    return _match_multi_scale(screen, template)


def _match_multi_scale(screen, template, scales=(1.0, 0.75, 0.5)):
    """多尺度金字塔匹配：模板缩放后在屏幕上匹配，取全局最高分。
    ⚡ 解决 DPI 缩放（125%/150%）与模拟器窗口缩放下单尺度必然失配的问题。"""
    best_val = -1.0
    best_center = None
    sh, sw = screen.shape[:2]
    for scale in scales:
        th = int(round(template.shape[0] * scale))
        tw = int(round(template.shape[1] * scale))
        if th < 2 or tw < 2 or th > sh or tw > sw:
            continue
        resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
        match_res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match_res)
        if max_val > best_val:
            best_val = max_val
            best_center = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
    return best_val, best_center


def resolve_template_string(text: Any, executor_ctx=None) -> Any:
    """
    ⚡ 模板变量替换引擎（统一 $ 前缀语法）
    推荐语法（所有输入框统一，不可省略 $ 前缀）:
      - 用户全局变量:   $var{name}
      - 节点上下文变量: $ctx{name}
      - 系统环境变量:   $env{name}（兼容 $sys{name}）
    旧语法兼容（历史数据）: {$var.name} / {$ctx.name} / {$env.name} / {$sys.name}
    注意：裸 {name} 不再识别为变量（必须带 $ 前缀）。
    """
    if not isinstance(text, str) or ('$' not in text and '{' not in text):
        return text

    # 新语法 $var{name} / $ctx{name} / $env{name} / $sys{name}；
    # 旧语法 {$var.name} / {$ctx.name} / {$env.name} / {$sys.name}
    pattern = re.compile(
        r'\$((?:var|ctx|env|sys))\{([^{}]*)\}'
        r'|\{(\$?(?:var|ctx|env|sys))\.([^{}]+)\}'
    )

    def replace_match(match):
        if match.group(1):
            namespace, key = match.group(1), match.group(2).strip()
        else:
            namespace, key = match.group(3).lstrip('$'), match.group(4).strip()
        namespace = namespace.lower()

        if namespace in ('env', 'sys'):
            return _resolve_env_var(key, executor_ctx, match.group(0))

        # var / ctx：统一查运行变量
        if executor_ctx and hasattr(executor_ctx, 'variables') and key in executor_ctx.variables:
            return str(executor_ctx.variables[key])
        return match.group(0)

    return pattern.sub(replace_match, text)


def _resolve_env_var(key: str, executor_ctx, raw: str) -> str:
    """系统环境变量解析；未命中返回原样"""
    if key in ('current_time', 'now'):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif key in ('time_short', 'time'):
        return datetime.now().strftime('%H:%M:%S')
    elif key in ('date', 'today'):
        return datetime.now().strftime('%Y-%m-%d')
    elif key == 'timestamp':
        return str(int(datetime.now().timestamp() * 1000))
    elif key == 'project_path':
        return getattr(executor_ctx, 'project_dir', '') or ''
    elif key == 'task_name':
        return getattr(executor_ctx, 'current_task_name', '') or ''
    elif key == 'node_name':
        current_node = getattr(executor_ctx, 'current_node', None)
        return getattr(current_node, 'node_name', '') if current_node else ''
    return raw
