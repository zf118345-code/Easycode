# core/conditions/handlers/text_contains.py
from typing import Any

from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register('text_contains')
class TextContainsEvaluator(BaseConditionEvaluator):
    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        raw_text = str(params.get('target_text', '')).strip()
        operator = str(params.get('exist_mode') or params.get('operator', 'contains')).strip().lower()
        gray_scale = bool(params.get('gray_scale', True))
        gray_threshold = int(params.get('gray_threshold', 127))

        if not raw_text:
            return False

        # ⚡ 调取工业级变量引擎解析目标文本
        target_text = resolve_template_string(raw_text, context)

        try:
            from core.node_executors.base.ocr_recognition import recognize_ocr_region

            recognized = recognize_ocr_region(
                context,
                region_type=params.get('region_type', 'fullwindow'),
                region_value=params.get('region_value'),
                region_reference_size=params.get('region_reference_size'),
                gray_scale=gray_scale,
                gray_threshold=gray_threshold,
            )
            detected_text = recognized['text']
            context.last_ocr_text = detected_text
            if hasattr(context, 'log'):
                if detected_text:
                    context.log(f'[OCR] 识别文字="{detected_text}"')
                else:
                    context.log(f'[OCR] 未识别到有效文字 | 区域={list(recognized["region"])}')

            if operator in ('contains', 'exists'):
                matched = target_text in detected_text
            elif operator in ('not_contains', 'not_exists'):
                matched = target_text not in detected_text
            elif operator in ('exact', 'equals'):
                matched = target_text == detected_text
            else:
                matched = False
            if hasattr(context, 'log'):
                labels = {
                    'contains': '包含', 'exists': '包含',
                    'not_contains': '不包含', 'not_exists': '不包含',
                    'exact': '完全等于', 'equals': '完全等于',
                }
                context.log(
                    f'[OCR] 目标条件={labels.get(operator, operator)}"{target_text}" | '
                    f'结果={"命中" if matched else "未命中"}'
                )
            return matched

        except Exception as e:
            if hasattr(context, 'log'):
                context.log(f' [OCR 判定失败]: {e}', 'warning')
            return False

        return False
