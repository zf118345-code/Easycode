# core/node_executors/base/page_state.py
# P2 新增：page_state 节点执行器
# 职责：评估当前屏幕是否匹配该页面的复合特征（AND/OR 组合）。
#   - 逐条评估 features 中的特征（统一通过 evaluate_condition 评估）
#   - 按 feature_mode（and/or）以及每条特征自带的 combine_mode 组合结果
#   - 匹配成功：将 page_id 写入 context.variables["current_page_id"]，走 on_success
#   - 匹配失败：走 on_failure
# exits 仅作为拓扑地图的出口元数据（供 GraphBuilder 构建邻接表 / smart_jump 寻路），
# 不在本执行器中直接驱动跳转。

import logging
from typing import Any

from core.conditions.evaluator import evaluate_condition
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

logger = logging.getLogger(__name__)


@NodeExecutorRegistry.register('page_state')
class PageStateNodeExecutor(BaseNodeExecutor):
    """页面状态节点执行器（拓扑画布）"""

    # 运行时默认参数（与 PARAM_DEFINITIONS 保持一致，供 merge_defaults 兜底）
    default_params: dict[str, Any] = {
        'page_id': '',
        'page_name': '',
        'features': [],
        'feature_mode': 'and',
        'exits': [],
    }

    def execute(self, node, context) -> dict[str, Any]:
        params = node.params or {}
        page_id = params.get('page_id', '') or ''
        page_name = params.get('page_name', '') or page_id
        features = params.get('features', []) or []
        feature_mode = (params.get('feature_mode', 'and') or 'and').lower()

        context.log(f'[page_state] 评估页面状态: {page_name} (page_id={page_id})，特征数={len(features)}')

        # 未定义任何特征时，视为不匹配，避免误判为"任意页面"
        if not features:
            context.log(f'[page_state] 页面 [{page_name}] 未定义任何特征，判定为不匹配', 'warning')
            return self.build_jump_result(
                success=False,
                jump_conf=node.on_failure,
                error='页面未定义特征',
                extra={'page_id': page_id, 'matched': False},
            )

        matched, detail = self._evaluate_features(features, feature_mode, context)
        context.log(f'[page_state] 页面 [{page_name}] 评估结果: {"匹配" if matched else "不匹配"} | {detail}')

        if matched:
            # 匹配成功：记录当前页面 ID，供 smart_jump 寻路使用
            context.variables['current_page_id'] = page_id
            context.log(f'[page_state] 已更新 current_page_id = {page_id}')
            return self.build_jump_result(
                success=True, jump_conf=node.on_success, extra={'page_id': page_id, 'matched': True}
            )

        return self.build_jump_result(
            success=False, jump_conf=node.on_failure, extra={'page_id': page_id, 'matched': False}
        )

    # ========== 特征评估 ==========

    def _evaluate_features(self, features: list[dict[str, Any]], feature_mode: str, context) -> tuple[bool, str]:
        """
        评估复合特征列表
        :return: (是否匹配, 评估明细字符串)
        """
        results: list[bool] = []

        for idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                results.append(False)
                continue

            # 将特征定义归一化为 evaluate_condition 可识别的条件字典
            cond = self._build_condition(feature)
            try:
                ok = bool(evaluate_condition(cond, context))
            except Exception as e:
                context.log(f'[page_state] 特征 #{idx + 1} 评估异常({cond.get("type")}): {e}', 'error')
                ok = False

            # 支持取反（描述"不存在某图/某文本"这类负向特征）
            if feature.get('negate'):
                ok = not ok

            results.append(ok)
            context.log(f'[page_state] 特征 #{idx + 1} ({cond.get("type")}) -> {ok}')

        return self._combine_results(results, features, feature_mode)

    @staticmethod
    def _build_condition(feature: dict[str, Any]) -> dict[str, Any]:
        """
        将特征定义归一化为 evaluate_condition 可识别的条件字典
        - feature_type / type 映射为条件的 type 字段
        - 展开 params 中的具体参数（template / text / region / threshold 等）
        - 兼容特征层级直接平铺参数的情况
        """
        cond: dict[str, Any] = {'type': feature.get('feature_type') or feature.get('type') or 'image_exists'}
        params = feature.get('params')
        if isinstance(params, dict):
            cond.update(params)
        # 兼容：特征层级直接平铺的参数
        for key in ('template', 'text', 'region', 'threshold', 'gray_scale', 'gray_threshold'):
            if key in feature:
                cond.setdefault(key, feature[key])
        return cond

    @staticmethod
    def _combine_results(results: list[bool], features: list[dict[str, Any]], feature_mode: str) -> tuple[bool, str]:
        """
        组合特征评估结果
        - 首条特征作为初始累积值
        - 后续特征优先使用自身 combine_mode，缺失时回退到全局 feature_mode
        """
        if not results:
            return False, '无特征'

        acc = results[0]
        detail_parts = [f'#1:{results[0]}']

        for i in range(1, len(results)):
            feat = features[i] if i < len(features) and isinstance(features[i], dict) else {}
            mode = (feat.get('combine_mode') or feature_mode).lower()
            if mode == 'or':
                acc = acc or results[i]
            else:
                acc = acc and results[i]
            detail_parts.append(f'({mode})#{i + 1}:{results[i]}')

        return acc, ' '.join(detail_parts)
