# core/conditions/handlers/image_exists.py
from typing import Any

from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.services.asset_service import AssetService
from core.services.runtime_target import capture_workspace, workspace_rect
from core.services.runtime_session import TemplateCache
from core.utils import load_image
from core.vision.frame_cache import prepared_frame
from core.vision.memory_matcher import MemoryTemplateMatcher


_CONDITION_TEMPLATE_CACHE = TemplateCache(max_entries=512)


@ConditionRegistry.register('image_exists')
class ImageExistsEvaluator(BaseConditionEvaluator):
    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        image_source = str(params.get('image_source', '')).strip()

        # 1. 规范化 exist_mode / operator
        raw_mode = str(params.get('exist_mode') or params.get('operator', 'exists')).lower()
        is_not_exists_mode = raw_mode in ('not_exists', 'not_exist', 'not_found')

        # 2. 规范化 threshold 阈值 (百分比自动除以 100)
        try:
            threshold = float(params.get('threshold', 0.8))
            if threshold > 1.0:
                threshold = threshold / 100.0
        except (ValueError, TypeError):
            threshold = 0.8

        project_dir = getattr(context, 'project_dir', None)

        if not image_source:
            if hasattr(context, 'last_match_score'):
                context.last_match_score = 0.0
            return False

        clean_name = image_source.replace('\\', '/')
        if clean_name.lower().endswith('.png'):
            clean_name = clean_name[:-4]

        # ⚡ 3. 核心升级：内存与磁盘双通道模板读取 (支持 DRM 零落盘加密模式)
        template_bgr = None

        # 通道 A: 尝试从 RAM 内存对象中提取已解密的模板矩阵
        # （字段名与 image_recognition 统一为 _memory_templates，由 execution_service 注入）
        memory_templates = getattr(context, '_memory_templates', None)
        if isinstance(memory_templates, dict) and clean_name in memory_templates:
            template_bgr = memory_templates[clean_name]

        # 通道 B: 内存未命中时，降级从磁盘模板目录读取 (Studio IDE 调试模式)
        resolved_asset = None
        if template_bgr is None and project_dir:
            try:
                resolved_asset = AssetService.resolve(project_dir, image_source)
                template_path = resolved_asset['full_path']
            except (FileNotFoundError, ValueError):
                template_path = ''
            if template_path:
                template_bgr, _ = _CONDITION_TEMPLATE_CACHE.get(template_path, load_image)
        elif project_dir:
            # Player 内存模板仍可复用项目资源登记中的录制区域元数据。
            try:
                resolved_asset = AssetService.resolve(project_dir, image_source, require_exists=False)
            except (FileNotFoundError, ValueError):
                resolved_asset = None

        if template_bgr is None:
            if hasattr(context, 'last_match_score'):
                context.last_match_score = 0.0
            if hasattr(context, 'log'):
                context.log(f' [识图条件] 无法获取模板矩阵 (内存与磁盘均未命中): {clean_name}', 'warning')
            return bool(is_not_exists_mode)

        try:
            # 4. 截取工作区图像 (BGR 格式)：与模板录制时的坐标系一致——
            # 模板是在「工作区截图」（窗口裁剪后）上框选的，region_value 为工作区相对坐标。
            # ⚡ 优先复用执行器本步共享截图（弹窗检测 + 页面评估同一帧），未缓存时自截
            shared = getattr(context, '_step_screen', None)
            if shared is not None:
                screen = shared
            else:
                screen = capture_workspace(context)
            screen_bgr = prepared_frame(context, screen)['bgr']

            # 5. 提取匹配区域参数
            region_type = str(params.get('region_type') or params.get('match_mode', 'fullwindow')).lower()
            region_value = params.get('region_value') or params.get('crop_rect') or params.get('region') or [0, 0, 0, 0]
            region_reference_size = params.get('region_reference_size')
            if region_type == 'recorded' and not cls._valid_region(region_value):
                capture = (resolved_asset or {}).get('record', {}).get('capture') or {}
                if cls._valid_region(capture.get('region')):
                    region_value = capture['region']
                    region_reference_size = capture.get('reference_size') or region_reference_size
            if region_type in {'recorded', 'custom'}:
                region_value = list(
                    workspace_rect(context, region_value, region_reference_size)
                )

            # ⚡ 6. 调取 MemoryTemplateMatcher 内存级比对引擎
            score, _ = MemoryTemplateMatcher.match_in_memory(
                screen_bgr=screen_bgr, template_bgr=template_bgr, region_type=region_type, region_value=region_value
            )

            # 强制将真实的得分回传至 context
            if hasattr(context, 'last_match_score'):
                context.last_match_score = score

            found = score >= threshold
        except Exception as exc:
            score = 0.0
            if hasattr(context, 'last_match_score'):
                context.last_match_score = 0.0
            if hasattr(context, 'log'):
                context.log(f' [识图条件] 工作区截图或匹配失败: {exc}', 'error')
            # 识别基础设施失败不等于“不存在”；所有操作符统一失败关闭，禁止 fail-open。
            return False

        return not found if is_not_exists_mode else found

    @staticmethod
    def _valid_region(value: Any) -> bool:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return False
        try:
            return float(value[2]) > 0 and float(value[3]) > 0
        except (TypeError, ValueError):
            return False
