# core/utils.py
import os
import sys
import json
import cv2
import numpy as np


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