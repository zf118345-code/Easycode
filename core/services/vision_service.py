# core/services/vision_service.py
import os
import json
import base64
import re
import win32gui
import pyautogui
from typing import Optional, List
from fastapi import HTTPException
from core.security import assert_safe_path, atomic_write_json

CONTEXT_FILE = "context.json"
REGIONS_FILE_PATH = os.path.join("templates", "regions.json")


class VisionService:

    @staticmethod
    def get_templates_tree(project_path: str) -> dict:
        templates_dir = os.path.join(project_path, "templates")
        if not os.path.exists(templates_dir):
            return {"tree": []}

        def build_tree(dir_path, relative_path=""):
            result = []
            try:
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    if os.path.isdir(item_path):
                        child_rel_path = os.path.join(relative_path, item).replace("\\", "/")
                        result.append({
                            "name": item,
                            "type": "directory",
                            "id": child_rel_path,
                            "children": build_tree(item_path, child_rel_path)
                        })
            except Exception as e:
                print(f"读取目录失败: {dir_path}, 错误: {e}")
            return result

        tree = build_tree(templates_dir, "")
        return {"tree": tree}

    @staticmethod
    def get_template_preview(project_path: str, relative_path: str = "") -> dict:
        templates_dir = os.path.join(project_path, "templates")
        full_target_dir = os.path.join(templates_dir, relative_path or "")
        target_dir = assert_safe_path(templates_dir, full_target_dir)

        if not os.path.exists(target_dir):
            return {"images": []}

        images = []
        try:
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isfile(item_path) and item.lower().endswith(".png"):
                    with open(item_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                        images.append({
                            "name": item,
                            "data": f"data:image/png;base64,{img_data}"
                        })
        except Exception as e:
            print(f"读取预览失败: {e}")

        return {"images": images}

    @staticmethod
    def get_image_thumb_path(project_path: str, name: str) -> str:
        if not project_path or not name:
            raise HTTPException(status_code=400, detail="缺少参数")

        clean_name = re.sub(r'\.png$', '', name, flags=re.IGNORECASE).replace("\\", "/")
        templates_dir = os.path.join(project_path, "templates")

        full_template_path = os.path.join(templates_dir, f"{clean_name}.png")
        if os.path.exists(full_template_path):
            return assert_safe_path(templates_dir, full_template_path)

        file_name_only = os.path.basename(clean_name)
        alt_paths = [
            os.path.join(templates_dir, "ocr", f"{file_name_only}.png"),
            os.path.join(templates_dir, f"{file_name_only}.png")
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                return assert_safe_path(templates_dir, alt_path)

        raise HTTPException(status_code=404, detail="缩略图不存在")

    @staticmethod
    def create_template_folder(project_path: str, parent_path: str, folder_name: str) -> dict:
        if not project_path or not folder_name:
            raise HTTPException(status_code=400, detail="文件夹名称不能为空")

        templates_dir = os.path.join(project_path, "templates")
        full_target_dir = os.path.join(templates_dir, parent_path or "", folder_name)
        target_dir = assert_safe_path(templates_dir, full_target_dir)

        # ⚡ 修复：当文件夹已存在时静默返回 success，不再报 400 Bad Request 错误
        if os.path.exists(target_dir):
            return {"status": "exists", "message": "文件夹已存在"}

        os.makedirs(target_dir, exist_ok=True)
        return {"status": "success"}

    @staticmethod
    def get_regions(project_path: str) -> dict:
        file_path = os.path.join(project_path, REGIONS_FILE_PATH)
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def save_region(project_path: str, template_name: str, crop_rect: List[int]) -> dict:
        clean_name = re.sub(r'\.png$', '', template_name, flags=re.IGNORECASE).replace("\\", "/")
        file_name_only = os.path.basename(clean_name)
        file_path = os.path.join(project_path, REGIONS_FILE_PATH)

        regions = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    regions = json.load(f)
            except Exception:
                regions = {}

        regions[clean_name] = crop_rect
        regions[file_name_only] = crop_rect
        atomic_write_json(file_path, regions)
        return {"status": "success"}

    @staticmethod
    def test_ocr(
        project_path: Optional[str],
        region_value: List[int],
        gray_scale: bool,
        gray_threshold: int,
        image_source: Optional[str] = ""
    ) -> dict:
        """
        ⚡ 极简精准测试逻辑：
        测试时如果已选择模板图片（image_source），直接对该模板图片进行二值化并抓字！
        实现所见即所得。如未选模板图片，再回退为截取屏幕 coordinates 视角。
        """
        import cv2
        import numpy as np
        from core.node_executors.base.ocr_recognition import get_ocr_engine

        frame_bgr = None

        # 1. 优先尝试加载选中的模板图片进行测试
        if project_path and image_source and image_source.strip():
            clean_name = re.sub(r'\.png$', '', image_source.strip(), flags=re.IGNORECASE).replace("\\", "/")
            templates_dir = os.path.join(project_path, "templates")

            template_path = os.path.join(templates_dir, f"{clean_name}.png")
            if not os.path.exists(template_path):
                file_name_only = os.path.basename(clean_name)
                alt_paths = [
                    os.path.join(templates_dir, "ocr", f"{file_name_only}.png"),
                    os.path.join(templates_dir, f"{file_name_only}.png")
                ]
                for p in alt_paths:
                    if os.path.exists(p):
                        template_path = p
                        break

            if os.path.exists(template_path):
                frame_bgr = cv2.imread(template_path, cv2.IMREAD_COLOR)

        # 2. 兜底逻辑：如果未选模板图片或文件不存在，去屏幕区域实时截图
        if frame_bgr is None:
            if len(region_value) == 4 and region_value[2] > 0 and region_value[3] > 0:
                x, y, w, h = region_value
                context_path = os.path.join(project_path, CONTEXT_FILE) if project_path else None
                if context_path and os.path.exists(context_path):
                    try:
                        with open(context_path, "r", encoding="utf-8") as f:
                            ctx = json.load(f)
                        window_title = ctx.get("window_title")
                        if window_title:
                            hwnd = win32gui.FindWindow(None, window_title)
                            if hwnd:
                                client_rect = win32gui.GetClientRect(hwnd)
                                wx, wy = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                                x += wx + ctx.get("offset_left", 0)
                                y += wy + ctx.get("offset_top", 0)
                    except Exception:
                        pass
                region_rect = (int(x), int(y), int(w), int(h))
            else:
                screen_w, screen_h = pyautogui.size()
                region_rect = (0, 0, screen_w, screen_h)

            screenshot = pyautogui.screenshot(region=region_rect)
            frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # 3. 进行灰度与二值化处理
        if gray_scale:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = frame_bgr

        # 4. 执行 OCR 识字
        engine_type, ocr_engine = get_ocr_engine()
        detected_text = ""
        if engine_type == "ddddocr" and ocr_engine:
            _, img_bytes = cv2.imencode('.png', processed_img)
            raw_res = ocr_engine.classification(img_bytes.tobytes())
            detected_text = str(raw_res).strip() if raw_res else ""
        else:
            detected_text = "未激活识别库"

        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        return {
            "status": "success",
            "text": detected_text,
            "image": img_b64
        }

    @staticmethod
    def test_image(project_path: str, template_name: str, gray_scale: bool, gray_threshold: int) -> dict:
        clean_name = re.sub(r'\.png$', '', template_name, flags=re.IGNORECASE).replace("\\", "/")
        templates_dir = os.path.join(project_path, "templates")

        template_path = os.path.join(templates_dir, f"{clean_name}.png")
        if not os.path.exists(template_path):
            file_name_only = os.path.basename(clean_name)
            alt_paths = [
                os.path.join(templates_dir, "ocr", f"{file_name_only}.png"),
                os.path.join(templates_dir, f"{file_name_only}.png")
            ]
            template_path = None
            for p in alt_paths:
                if os.path.exists(p):
                    template_path = p
                    break

            if not template_path:
                return {"status": "not_found", "image": ""}

        import cv2

        template_bgr = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template_bgr is None:
            return {"status": "read_error", "image": ""}

        if gray_scale:
            gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = template_bgr

        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')
        return {"status": "success", "image": img_b64}