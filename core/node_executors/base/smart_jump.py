# core/node_executors/base/smart_jump.py
# P2 新增：smart_jump 节点执行器（主流程专属）
# 职责：业务人员只需指定目标页面，底层自动完成：
#   - 当前页面判定：优先读取 current_page_id，缺失时现场评估所有拓扑页面（page_state 特征匹配）
#   - 在拓扑地图上寻路（混合图 BFS 最短路径，PathFinder）
#   - 将路径写入 context.variables["__smart_jump_path__"]，由 GraphExecutor 沿路径执行
#     （逐节点执行操作 / 页面确认，每步监测位置，偏离时从当前位置重新寻路）
#
# 路径的实际逐节点执行在 GraphExecutor._execute_smart_jump_path（见 core/executor.py）。

import logging
from typing import Any

from core.graph.pathfinder import PathResult
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

logger = logging.getLogger(__name__)


@NodeExecutorRegistry.register('smart_jump')
class SmartJumpNodeExecutor(BaseNodeExecutor):
    """智能跳转节点执行器（工作流画布）"""

    # 存放本次 smart_jump 计算出的路径的变量键（GraphExecutor 消费）
    PATH_VAR_KEY = '__smart_jump_path__'

    # 运行时默认参数（与 PARAM_DEFINITIONS 保持一致，供 merge_defaults 兜底）
    default_params: dict[str, Any] = {
        'target_page_id': '',
        'timeout': 3000,
    }

    def execute(self, node, context) -> dict[str, Any]:
        params = node.params or {}

        # 解析统一表达式（$var{name} / $ctx{name} / $env{name}）
        target_page_id = self._resolve(params.get('target_page_id'), context)
        timeout = max(100, int(params.get('timeout', 3000) or 3000))

        context.log(f'[智能跳转] 启动智能跳转 | 目标页面=[{context._topology_page_label(target_page_id)}] 超时={timeout}ms')

        if not target_page_id:
            context.log('[智能跳转] 未配置目标页面', 'error')
            return self.build_result(success=False, error='未配置目标页面')

        # current_page_id 仅作为识别排序提示，智能跳转必须现场验证，避免点击后沿用陈旧缓存。
        cached_page = context.variables.get('current_page_id', '')
        if cached_page:
            context.log(f'[智能跳转] 缓存页面仅作候选提示: [{context._topology_page_label(cached_page)}]，开始现场验证...')
        else:
            context.log(f'[智能跳转] 加载等待评估当前页面（超时 {timeout}ms）...')
        current_page = context._resolve_current_page_with_load_wait(timeout)
        if current_page:
            context.variables['current_page_id'] = current_page
            context.log(f'[智能跳转] 现场评估命中当前页面: [{context._topology_page_label(current_page)}]')
        else:
            context.log('[智能跳转] 加载等待超时，未命中任何已知页面，无法确定当前位置', 'warning')

        if not current_page:
            return self.build_result(success=False, error='无法确定当前页面')

        # 已在目标页面：无需跳转
        if current_page == target_page_id:
            context.log(f'[智能跳转] 已在目标页面 [{context._topology_page_label(target_page_id)}]，无需跳转')
            return self.build_result(
                success=True,
                extra={'target_page_id': target_page_id, 'path': [target_page_id]},
            )

        # 拓扑地图寻路（混合图 BFS 最短路径）
        path_result = self._compute_path(target_page_id, context)

        if not path_result.success or not path_result.path or len(path_result.path) < 2:
            reason = path_result.reason or '路径为空'
            context.log(f'[智能跳转] 从 [{context._topology_page_label(current_page)}] 到 [{context._topology_page_label(target_page_id)}] 寻路失败: {reason}', 'error')
            return self.build_result(
                success=False,
                error=f'寻路失败: {reason}',
                extra={'target_page_id': target_page_id},
            )

        # 写入路径，交由 GraphExecutor 沿路径执行（每步监测位置、动态重算）
        context.variables[self.PATH_VAR_KEY] = {
            'path': path_result.path,
            'target_page_id': target_page_id,
            'timeout': timeout,
            # execute 返回后 GraphExecutor 会同步消费路径，中间没有用户操作点；
            # 路径执行首轮可复用这个刚刚现场验证过的起点，避免重复扫描耗尽超时。
            'verified_page_id': current_page,
        }
        context.log(f'[智能跳转] 寻路成功 | 路径: {" → ".join(context._topology_page_label(x) for x in path_result.path)}')
        return self.build_result(
            success=True,
            extra={'path': path_result.path, 'target_page_id': target_page_id},
        )

    # ========== 寻路核心 ==========

    @staticmethod
    def _compute_path(target_page_id: str, context) -> PathResult:
        """在拓扑地图上寻找从当前位置到目标页面的最短路径"""
        return context.find_path_to_page(target_page_id)

    # ========== 辅助 ==========

    @staticmethod
    def _resolve(value: Any, context) -> str:
        """解析统一变量表达式，None 安全。"""
        if value is None:
            return ''
        return str(context.parse_expr(value))
