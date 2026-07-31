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