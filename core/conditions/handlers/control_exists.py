# core/conditions/handlers/control_exists.py
# ⚡ 存在控件 / 不存在控件 判定（logic_check / branch / 页面特征通用）
import re
from typing import Any

from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register('control_exists')
class ControlExistsEvaluator(BaseConditionEvaluator):
    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        raw_target = str(params.get('target', '')).strip()
        exist_mode = str(params.get('exist_mode') or params.get('operator', 'exists'))
        if not raw_target:
            return False

        target = resolve_template_string(raw_target, context).strip()
        window_title = resolve_template_string(str(params.get('window_title', '')), context).strip()
        by = str(params.get('by', 'uia_name')).strip()
        try:
            index = int(params.get('index', 0) or 0)
        except (TypeError, ValueError):
            index = 0
        try:
            timeout_ms = int(params.get('timeout', 3000) or 3000)
        except (TypeError, ValueError):
            timeout_ms = 3000

        # ⚡ 捕获格式 name="x"/type="x"/id="x"/class="x" → 自动推断 UIA 查找方式
        by, target = cls._infer_selector(by, target)
        if not target:
            return False

        if by.startswith('uia_'):
            from core.services import uia_service

            info = None
            # 祖先链优先：捕获时记录的路径逐级下降定位（毫秒级）；失效回退 BFS
            control_info = params.get('control_info') or {}
            path = control_info.get('ancestor_path') if isinstance(control_info, dict) else None
            if isinstance(path, list) and path:
                info = uia_service.find_control_by_path(
                    window_title=window_title, path=path, timeout_ms=min(timeout_ms, 1500)
                )
            # 位置锚点：固定位置控件 rect 中心命中 + 身份校验
            if info is None and isinstance(control_info, dict):
                info = uia_service.find_control_by_rect(
                    control_info.get('rect'),
                    expect_name=control_info.get('name'),
                    expect_aid=control_info.get('automation_id'),
                    expect_type=control_info.get('control_type'),
                )
            if info is None:
                info = uia_service.find_control(
                    window_title=window_title, by=by, target=target, index=index, timeout_ms=timeout_ms
                )
        else:
            from core.services.control_service import find_control

            info = find_control(
                window_title=window_title, by=by, target=target, index=index, timeout_ms=timeout_ms
            )

        found = info is not None

        # ⚡ branch best 策略得分（命中 1.0 / 未命中 0.0）
        try:
            context.last_match_score = 1.0 if found else 0.0
        except Exception:
            pass

        if exist_mode in ('exists', 'exist'):
            return found
        if exist_mode in ('not_exists', 'not_exist', 'not_found'):
            return not found
        return False

    @staticmethod
    def _infer_selector(by, target):
        """捕获格式 name="x"/type="x"/id="x"/class="x" → UIA 查找方式"""
        m = re.match(r'^(name|type|id|class)="([^"]*)"$', target)
        if m and not by.startswith('uia_'):
            kind, value = m.group(1), m.group(2).strip()
            mapping = {'name': 'uia_name', 'type': 'uia_type', 'id': 'uia_id', 'class': 'uia_class'}
            return mapping[kind], value
        return by, target
