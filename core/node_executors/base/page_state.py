# core/node_executors/base/page_state.py
# P2 新增：page_state 节点执行器
# 职责：评估当前屏幕是否匹配该页面的复合特征（AND/OR 组合）。
#   - 逐条评估 features 中的特征（统一通过 evaluate_condition 评估）
#   - 所有特征只按页面节点的 feature_mode（and/or）统一组合
#   - 匹配成功：将 page_id 写入 context.variables["current_page_id"]
# 跳转由 topology.json 的实体边负责。

import logging
from typing import Any

from core.conditions.evaluator import evaluate_condition
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

logger = logging.getLogger(__name__)

# ⚡ 条件类型中文映射（日志可读化）
_CONDITION_LABELS = {
    'image_exists': '图像存在',
    'image_not_exists': '图像不存在',
    'text_contains': '文本包含',
    'text_not_contains': '文本不包含',
    'ocr_exists': '文字识别',
    'control_exists': '控件存在',
    'control_not_exists': '控件不存在',
    'file_exists': '文件检查',
    'variable_check': '变量判断',
    'logic_check': '逻辑判断',
}


@NodeExecutorRegistry.register('page_state')
class PageStateNodeExecutor(BaseNodeExecutor):
    """页面状态节点执行器（拓扑画布）"""

    # 运行时默认参数（与 PARAM_DEFINITIONS 保持一致，供 merge_defaults 兜底）
    # 页面名称 = 节点标题；出口 = 拓扑连线（边即出口），均不再是节点参数
    default_params: dict[str, Any] = {
        'page_id': '',
        'features': [],
        'feature_mode': 'and',
    }

    def execute(self, node, context) -> dict[str, Any]:
        params = node.params or {}
        page_id = params.get('page_id', '') or ''
        features = params.get('features', []) or []
        feature_mode = (params.get('feature_mode', 'and') or 'and').lower()

        page_name = getattr(node, 'node_name', '') or page_id

        context.log(f'[页面状态] 评估页面: [{page_name}]，特征数={len(features)}')

        # 未定义任何特征时，视为不匹配，避免误判为"任意页面"
        if not features:
            context.log(f'[页面状态] 页面 [{page_name}] 未定义任何特征，判定为不匹配', 'warning')
            return self.build_result(
                success=False,
                error='页面未定义特征',
                extra={'page_id': page_id, 'matched': False},
            )

        matched, detail = self._evaluate_features(features, feature_mode, context)
        context.log(f'[页面状态] 页面 [{page_name}] 评估结果: {"✓ 匹配" if matched else "✗ 不匹配"} | {detail}')

        if matched:
            # 匹配成功：记录当前页面 ID，供 smart_jump 寻路使用
            context.variables['current_page_id'] = page_id
            context.log(f'[页面状态] 已定位当前页面: {page_name}')
            return self.build_result(success=True, extra={'page_id': page_id, 'matched': True})

        return self.build_result(success=False, extra={'page_id': page_id, 'matched': False})

    # ========== 特征评估 ==========

    def _evaluate_features(self, features: list[dict[str, Any]], feature_mode: str, context) -> tuple[bool, str]:
        """
        评估复合特征列表
        :return: (是否匹配, 评估明细字符串)
        """
        results: list[bool] = []
        mode = 'or' if str(feature_mode or 'and').lower() == 'or' else 'and'
        get_setting = getattr(context, 'get_setting', None)
        full_diagnostics = bool(get_setting('diagnostic_full_page_evaluation', False)) if callable(get_setting) else False

        for idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                results.append(False)
                continue

            # 将特征定义归一化为 evaluate_condition 可识别的条件字典
            cond = self._build_condition(feature)
            cond_label = _CONDITION_LABELS.get(cond.get('condition_type'), cond.get('condition_type'))
            try:
                # ⚡ 评估前清零得分，评估后读取（image_exists 会把匹配置信度写回 context.last_match_score）
                if hasattr(context, 'last_match_score'):
                    context.last_match_score = 0.0
                ok = bool(evaluate_condition(cond, context))
                score = float(getattr(context, 'last_match_score', 0.0) or 0.0)
            except Exception as e:
                context.log(f'[页面状态] 特征 #{idx + 1} ({cond_label}) 评估异常: {e}', 'error')
                ok = False
                score = 0.0

            # 支持取反（描述"不存在某图/某文本"这类负向特征）
            if feature.get('negate'):
                ok = not ok

            results.append(ok)
            # ⚡ 匹配分数进日志：图像特征显示置信度，方便排障（最接近页面差多少一目了然）
            if cond.get('condition_type') == 'image_exists' and score > 0:
                context.log(
                    f'[页面状态] 特征 #{idx + 1} ({cond_label}) -> {"✓ 命中" if ok else "✗ 未命中"} | 置信度 {score:.2f}'
                )
            else:
                context.log(
                    f'[页面状态] 特征 #{idx + 1} ({cond_label}) -> {"✓ 命中" if ok else "✗ 未命中"}'
                )

            if not full_diagnostics and ((mode == 'and' and not ok) or (mode == 'or' and ok)):
                skipped = len(features) - idx - 1
                if skipped > 0:
                    context.log(f'[页面状态] {mode.upper()} 已确定结果，跳过剩余 {skipped} 个特征')
                break

        return self._combine_results(results, features[:len(results)], feature_mode)

    @staticmethod
    def _build_condition(feature: dict[str, Any]) -> dict[str, Any]:
        """
        将特征定义归一化为 evaluate_condition 可识别的条件字典
        - condition_type 映射为条件的 type 字段
        - 条件参数使用平铺结构
        - 页面组合键由页面节点统一消费；旧的 combine_mode 永远不进入条件参数
        """
        cond: dict[str, Any] = {'condition_type': feature.get('condition_type') or 'image_exists'}
        for key, value in feature.items():
            if key in ('condition_type', 'combine_mode', 'negate'):
                continue
            if key not in cond:
                cond[key] = value
        # 捕获生成的页面特征只要带有有效录制区域，就应使用该区域匹配。
        # 旧数据有时同时保存 crop_rect/region，却误写为 fullwindow；这里按
        # 明确的捕获元数据纠正，手工创建且没有捕获元数据的 fullwindow 不受影响。
        region = cond.get('region_value')
        captured_region = cond.get('crop_rect') or cond.get('region')
        if (
            cond.get('condition_type') == 'image_exists'
            and str(cond.get('region_type') or '').lower() == 'fullwindow'
            and isinstance(region, list) and len(region) == 4
            and float(region[2] or 0) > 0 and float(region[3] or 0) > 0
            and isinstance(captured_region, list) and len(captured_region) == 4
        ):
            cond['region_type'] = 'recorded'
        return cond

    @staticmethod
    def _combine_results(results: list[bool], features: list[dict[str, Any]], feature_mode: str) -> tuple[bool, str]:
        """
        组合特征评估结果
        页面节点是唯一组合语义来源；单条特征不允许覆盖 AND/OR。
        """
        if not results:
            return False, '无特征'

        mode = 'or' if str(feature_mode or 'and').lower() == 'or' else 'and'
        matched = any(results) if mode == 'or' else all(results)
        detail = f' {mode} '.join(f'#{index + 1}:{value}' for index, value in enumerate(results))
        return matched, detail
