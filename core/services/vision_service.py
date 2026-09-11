# core/services/vision_service.py
import base64
import os

import numpy as np
from fastapi import HTTPException

from core.security import assert_safe_path
from core.services.asset_service import AssetService
from core.services.template_library_service import TemplateLibraryService
from core.utils import load_image

CONTEXT_FILE = 'context.json'


class VisionService:
    @staticmethod
    def _capture_project_workspace(project_path: str | None):
        """使用与运行引擎相同的目标绑定截取工作面板，失败时拒绝冒充全屏。"""
        ctx = {}
        if project_path:
            from core.services.workspace_service import WorkspaceService

            ctx = WorkspaceService.load_runtime_context(project_path)
        # 局部导入以避免 WorkspaceService -> VisionService 的模块初始化环。
        from core.services.workspace_service import WorkspaceService

        image, _ = WorkspaceService._capture_context_image(ctx)
        return image

    @staticmethod
    def _scale_region(region_value, reference_size, current_size):
        """把录制时工作面板像素区域映射到当前工作面板。"""
        values = list(region_value or [0, 0, 0, 0])
        if len(values) != 4:
            raise HTTPException(status_code=400, detail='识别区域必须是 [X, Y, W, H]')
        try:
            x, y, width, height = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail='识别区域包含非数字坐标') from exc

        ref = list(reference_size or [0, 0])
        if len(ref) >= 2 and float(ref[0] or 0) > 0 and float(ref[1] or 0) > 0:
            scale_x = float(current_size[0]) / float(ref[0])
            scale_y = float(current_size[1]) / float(ref[1])
            x, width = x * scale_x, width * scale_x
            y, height = y * scale_y, height * scale_y

        left, top = int(round(x)), int(round(y))
        right, bottom = int(round(x + width)), int(round(y + height))
        if left < 0 or top < 0 or right > current_size[0] or bottom > current_size[1] or right <= left or bottom <= top:
            raise HTTPException(
                status_code=400,
                detail=f'识别区域超出当前工作面板: {[left, top, right - left, bottom - top]} / {list(current_size)}',
            )
        return left, top, right, bottom

    @staticmethod
    def get_templates_tree(project_path: str) -> dict:
        templates_dir = AssetService.templates_dir(project_path)
        if not os.path.isdir(templates_dir):
            raise HTTPException(status_code=422, detail='项目资源目录不存在，请先修复项目')

        def build_tree(dir_path, relative_path=''):
            result = []
            try:
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    if os.path.isdir(item_path):
                        child_rel_path = os.path.join(relative_path, item).replace('\\', '/')
                        result.append({
                            'name': item,
                            'type': 'directory',
                            'id': child_rel_path,
                            'protected': child_rel_path in TemplateLibraryService.PROTECTED_ROOTS,
                            'children': build_tree(item_path, child_rel_path),
                        })
            except Exception as e:
                print(f'读取目录失败: {dir_path}, 错误: {e}')
            return result

        tree = build_tree(templates_dir, '')
        return {'tree': tree}

    @staticmethod
    def get_template_preview(project_path: str, relative_path: str = '') -> dict:
        templates_dir = AssetService.templates_dir(project_path)
        if not os.path.isdir(templates_dir):
            raise HTTPException(status_code=422, detail='项目资源目录不存在，请先修复项目')
        full_target_dir = os.path.join(templates_dir, relative_path or '')
        target_dir = assert_safe_path(templates_dir, full_target_dir)

        if not os.path.exists(target_dir):
            return {'images': []}

        images = []
        registered = AssetService.metadata_for_directory(project_path, relative_path)
        try:
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isfile(item_path) and item.lower().endswith(('.png', '.jpg', '.jpeg')):
                    rel = '/'.join(part for part in (relative_path.strip('/'), item) if part)
                    asset = registered.get(rel.casefold()) or {}
                    images.append({
                        'name': item,
                        'relative_path': rel,
                        'asset_id': asset.get('id', ''),
                        'asset_ref': asset.get('asset_ref', ''),
                        'kind': asset.get('kind', ''),
                    })
        except Exception as e:
            print(f'读取预览失败: {e}')

        return {'images': images}

    @staticmethod
    def get_image_thumb_path(project_path: str, name: str) -> str:
        if not project_path or not name:
            raise HTTPException(status_code=400, detail='缺少参数')
        try:
            return AssetService.resolve(project_path, name)['full_path']
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @staticmethod
    def register_template(project_path: str, relative_path: str, kind: str = '') -> dict:
        try:
            record = AssetService.register_file(project_path, relative_path, kind or None)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            'asset_id': record['id'],
            'asset_ref': AssetService.reference(record['id']),
            'path': record['path'],
            'kind': record['kind'],
        }

    @staticmethod
    def resolve_template(project_path: str, reference: str) -> dict:
        try:
            resolved = AssetService.resolve(project_path, reference)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        record = resolved.get('record') or {}
        capture = record.get('capture') if isinstance(record.get('capture'), dict) else {}
        return {
            'asset_id': resolved.get('asset_id', ''),
            'asset_ref': resolved.get('asset_ref', ''),
            'path': resolved['relative_path'],
            'key': resolved['key'],
            'kind': record.get('kind') or AssetService.infer_kind(resolved['relative_path']),
            'display_name': record.get('display_name') or os.path.basename(resolved['key']),
            'width': record.get('width'),
            'height': record.get('height'),
            'capture': {
                'region': list(capture.get('region') or []),
                'reference_size': list(capture.get('reference_size') or []),
                'coordinate_space': capture.get('coordinate_space') or 'workspace_px',
            } if capture else None,
        }

    @staticmethod
    def create_template_folder(project_path: str, parent_path: str, folder_name: str) -> dict:
        if not project_path or not folder_name:
            raise HTTPException(status_code=400, detail='文件夹名称不能为空')

        try:
            clean_name = TemplateLibraryService._validate_name(folder_name)
            clean_parent = TemplateLibraryService._normalize_library_path(parent_path, allow_root=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not clean_parent and clean_name not in TemplateLibraryService.PROTECTED_ROOTS:
            raise HTTPException(status_code=400, detail='请先选择 image、ocr 或 page 分类，再新建子文件夹')
        if clean_parent:
            top = clean_parent.split('/', 1)[0]
            if top not in TemplateLibraryService.PROTECTED_ROOTS:
                raise HTTPException(status_code=400, detail='文件夹必须创建在 image、ocr 或 page 分类内')

        templates_dir = AssetService.ensure_structure(project_path)
        full_target_dir = os.path.join(templates_dir, clean_parent.replace('/', os.sep), clean_name)
        target_dir = assert_safe_path(templates_dir, full_target_dir)

        # ⚡ 修复：当文件夹已存在时静默返回 success，不再报 400 Bad Request 错误
        if os.path.exists(target_dir):
            return {'status': 'exists', 'message': '文件夹已存在'}

        os.makedirs(target_dir, exist_ok=True)
        return {'status': 'success'}

    @staticmethod
    def inspect_template_mutation(project_path: str, relative_path: str) -> dict:
        try:
            return TemplateLibraryService.inspect(project_path, relative_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def delete_template_entry(project_path: str, relative_path: str) -> dict:
        try:
            return TemplateLibraryService.delete(project_path, relative_path)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def move_template_entry(
        project_path: str,
        relative_path: str,
        target_parent_path: str,
        new_name: str = '',
    ) -> dict:
        try:
            return TemplateLibraryService.move(
                project_path, relative_path, target_parent_path, new_name,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def list_template_trash(project_path: str) -> dict:
        return TemplateLibraryService.list_trash(project_path)

    @staticmethod
    def restore_template_entry(project_path: str, transaction_id: str) -> dict:
        try:
            return TemplateLibraryService.restore(project_path, transaction_id)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def get_regions(project_path: str) -> dict:
        regions: dict = {}
        metadata: dict = {}
        for asset_id, record in AssetService.load_registry(project_path).get('assets', {}).items():
            capture = record.get('capture') if isinstance(record, dict) else None
            if not isinstance(capture, dict) or not isinstance(capture.get('region'), list):
                continue
            reference = AssetService.reference(asset_id)
            regions[reference] = capture['region']
            metadata[reference] = {
                'reference_size': capture.get('reference_size') or [0, 0],
                'coordinate_space': capture.get('coordinate_space') or 'workspace_px',
            }
        if metadata:
            regions['__meta__'] = metadata
        return regions

    @staticmethod
    def save_region(
        project_path: str,
        template_name: str,
        crop_rect: list[int],
        reference_size: list[int] | tuple[int, int] | None = None,
    ) -> dict:
        if not AssetService.is_asset_reference(template_name):
            raise ValueError('截图区域只能绑定到 asset:// 稳定资源引用')
        AssetService.update_capture(project_path, template_name, {
            'region': crop_rect,
            'reference_size': list(reference_size or [0, 0])[:2],
            'coordinate_space': 'workspace_px',
        })
        return {'status': 'success'}

    @staticmethod
    def test_ocr(
        project_path: str | None,
        region_value: list[int],
        gray_scale: bool,
        gray_threshold: int,
        image_source: str | None = '',
        region_reference_size: list[int] | None = None,
    ) -> dict:
        """
        ⚡ 极简精准测试逻辑：
        测试时如果已选择模板图片（image_source），直接对该模板图片进行二值化并抓字！
        实现所见即所得。如未选模板图片，再回退为截取屏幕 coordinates 视角。
        """
        import cv2
        import numpy as np

        from core.vision.ocr_engine import get_ocr_engine

        frame_bgr = None

        # 1. 优先尝试加载选中的模板图片进行测试
        if project_path and image_source and image_source.strip():
            try:
                template_path = AssetService.resolve(project_path, image_source.strip())['full_path']
            except (FileNotFoundError, ValueError):
                template_path = ''
            if template_path:
                frame_bgr = load_image(template_path, cv2.IMREAD_COLOR)

        # 2. 兜底逻辑：如果未选模板图片或文件不存在，严格截取项目绑定的工作面板
        if frame_bgr is None:
            screenshot = VisionService._capture_project_workspace(project_path)
            if len(region_value or []) == 4 and region_value[2] > 0 and region_value[3] > 0:
                crop_box = VisionService._scale_region(
                    region_value,
                    region_reference_size,
                    (screenshot.width, screenshot.height),
                )
                screenshot = screenshot.crop(crop_box)
            frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # 3. 进行灰度与二值化处理
        if gray_scale:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = frame_bgr

        # 4. 执行 OCR 识字（⚡ #2 统一识别入口：RapidOCR 优先，ddddocr 兜底；引擎缺失时明确提示）
        from core.vision.ocr_engine import ocr_engine_recognize

        detected_text = ocr_engine_recognize(processed_img).strip()
        if not detected_text:
            engine_type, _ = get_ocr_engine()
            if engine_type == 'none':
                detected_text = '未激活识别库（rapidocr/ddddocr 均未安装）'

        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = 'data:image/png;base64,' + base64.b64encode(buffer).decode('utf-8')

        return {'status': 'success', 'text': detected_text, 'image': img_b64}

    @staticmethod
    def test_image(
        project_path: str, template_name: str, gray_scale: bool, gray_threshold: int,
        region_type: str = 'fullwindow', region_value: list = None,
        region_reference_size: list[int] | None = None,
        preview_only: bool = False,
    ) -> dict:
        """图像识别测试：模板预览 + 工作区实时匹配（返回置信度与命中位置）。
        ⚡ 区域匹配与执行引擎一致：优先按项目 context 定位工作区截图（region_value 为工作区相对坐标），
        无窗口上下文时全屏截图兜底。"""
        try:
            template_path = AssetService.resolve(project_path, template_name)['full_path']
        except (FileNotFoundError, ValueError):
            return {'status': 'not_found', 'image': ''}

        import cv2

        try:
            template_bgr = load_image(template_path, cv2.IMREAD_COLOR)
        except FileNotFoundError:
            return {'status': 'read_error', 'image': ''}

        # 属性面板中的二值化缩略图只处理模板本身，不读取实时工作窗口。
        # 最小化检查仅属于主动“测试识别/截图捕获”，不能阻断普通文件选择。
        if gray_scale:
            gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = template_bgr
        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = 'data:image/png;base64,' + base64.b64encode(buffer).decode('utf-8')
        if preview_only:
            return {
                'status': 'success',
                'image': img_b64,
                'confidence': None,
                'center_pos': None,
            }

        # ⚡ 实时匹配：工作区截图（与执行引擎坐标系一致）→ 区域裁剪 → 模板匹配
        confidence = 0.0
        center_pos = None
        screen_img = None
        from core.vision.memory_matcher import MemoryTemplateMatcher

        screen_img = VisionService._capture_project_workspace(project_path)
        screen_bgr = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)
        rt = str(region_type or 'fullwindow').lower()
        if rt == 'fullwindow':
            rv = [0, 0, screen_bgr.shape[1], screen_bgr.shape[0]]
        else:
            left, top, right, bottom = VisionService._scale_region(
                region_value,
                region_reference_size,
                (screen_bgr.shape[1], screen_bgr.shape[0]),
            )
            rv = [left, top, right - left, bottom - top]
        confidence, center_pos = MemoryTemplateMatcher.match_in_memory(
            screen_bgr=screen_bgr, template_bgr=template_bgr, region_type='custom', region_value=rv
        )

        return {
            'status': 'success',
            'image': img_b64,
            'confidence': round(float(confidence or 0.0), 4),
            'center_pos': list(center_pos) if center_pos else None,
        }
