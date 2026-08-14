# core/node_executors/base/smart_jump.py
# P2 新增：smart_jump 节点执行器
# 职责：业务人员只需指定目标页面（或目标节点），底层自动寻路。
#   - 优先按 target_node_id 在工作流图寻路（find_path_to_node）
#   - 否则按 target_page_id 在拓扑地图寻路（find_path_to_page）
#   - 找到路径后写入 context.variables["__smart_jump_path__"]，供后续迭代逐步执行
#   - 支持重试（max_retries）与超时（timeout）
#   - clear_obstacles 开启时，每次重试前尝试清理弹窗阻碍（简化实现）
#
# 说明：本版本为"简化版"——计算并记录路径后即返回成功，
# 路径上各动作的实际逐节点执行由后续迭代完成（通过 __smart_jump_path__ 中的 pending 队列驱动）。

import logging
import time
from typing import Any

from core.graph.pathfinder import PathResult
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry

logger = logging.getLogger(__name__)


@NodeExecutorRegistry.register('smart_jump')
class SmartJumpNodeExecutor(BaseNodeExecutor):
    """智能跳转节点执行器（工作流画布）"""

    # 存放本次 smart_jump 计算出的路径的变量键
    PATH_VAR_KEY = '__smart_jump_path__'

    # 运行时默认参数（与 PARAM_DEFINITIONS 保持一致，供 merge_defaults 兜底）
    default_params: dict[str, Any] = {
        'target_page_id': '',
        'target_task_id': '',
        'target_node_id': '',
        'path_strategy': 'shortest',
        'max_retries': 3,
        'clear_obstacles': True,
        'timeout': 30,
    }

    def execute(self, node, context) -> dict[str, Any]:
        params = node.params or {}

        # 解析参数（支持 ${var} 模板）
        target_page_id = self._resolve(params.get('target_page_id'), context)
        target_task_id = self._resolve(params.get('target_task_id'), context)
        target_node_id = self._resolve(params.get('target_node_id'), context)
        path_strategy = params.get('path_strategy', 'shortest') or 'shortest'
        max_retries = max(0, int(params.get('max_retries', 3)))
        clear_obstacles = bool(params.get('clear_obstacles', True))
        timeout = max(1, int(params.get('timeout', 30)))

        current_page = context.variables.get('current_page_id', '')
        context.log(
            f'[smart_jump] 启动智能跳转 | 当前页面={current_page or "-"} '
            f'目标页面={target_page_id or "-"} 目标任务={target_task_id or "-"} '
            f'目标节点={target_node_id or "-"} 策略={path_strategy} '
            f'重试={max_retries} 超时={timeout}s'
        )

        # 校验：至少指定一种目标
        if not target_page_id and not target_node_id:
            context.log('[smart_jump] 未指定 target_page_id 或 target_node_id', 'error')
            return self.build_jump_result(
                success=False, jump_conf=(node.params or {}).get('on_failure'), error='未指定跳转目标'
            )

        deadline = time.time() + timeout
        attempt = 0
        last_reason = ''

        while attempt < max_retries and time.time() < deadline:
            attempt += 1

            # 响应停止信号
            if context.is_stopped:
                context.log('[smart_jump] 收到停止信号，终止寻路', 'warning')
                break

            # 计算路径
            path_result = self._compute_path(target_node_id, target_task_id, target_page_id, context)

            if path_result.success and path_result.path:
                # 找到路径：写入变量并返回成功
                path_info: dict[str, Any] = {
                    'path': path_result.path,
                    'edges': path_result.edges,
                    'strategy': path_strategy,
                    'target_page_id': target_page_id,
                    'target_node_id': target_node_id,
                    'target_task_id': target_task_id,
                    'attempt': attempt,
                    'executed': [],  # 已执行的步骤（后续迭代填充）
                    'pending': list(path_result.path[1:]),  # 待执行（不含起点）
                }
                context.variables[self.PATH_VAR_KEY] = path_info
                context.log(f'[smart_jump] 寻路成功（第 {attempt} 次）| 路径: {" -> ".join(path_result.path)}')

                # 简化版：仅记录路径，实际逐节点执行由后续迭代完成
                return self.build_jump_result(
                    success=True,
                    jump_conf=(node.params or {}).get('on_success'),
                    extra={'path': path_result.path, 'path_edges': path_result.edges, 'strategy': path_strategy},
                )

            last_reason = path_result.reason or '未知原因'
            context.log(f'[smart_jump] 第 {attempt}/{max_retries} 次寻路失败: {last_reason}', 'warning')

            # 重试前尝试清理弹窗阻碍
            if clear_obstacles and attempt < max_retries:
                self._clear_obstacles(context)

            # 短暂等待后重试（不超过剩余超时）
            if attempt < max_retries and time.time() < deadline:
                remaining = max(0.0, deadline - time.time())
                time.sleep(min(1.0, remaining))

        # 全部重试失败
        context.log(f'[smart_jump] 智能跳转失败，已达最大重试次数 | 原因: {last_reason}', 'error')
        return self.build_jump_result(
            success=False,
            jump_conf=(node.params or {}).get('on_failure'),
            error=f'寻路失败: {last_reason}',
            extra={'attempts': attempt, 'target_page_id': target_page_id, 'target_node_id': target_node_id},
        )

    # ========== 寻路核心 ==========

    def _compute_path(self, target_node_id: str, target_task_id: str, target_page_id: str, context) -> PathResult:
        """
        根据目标类型选择寻路方式
        - target_node_id 优先：在工作流图上寻路到目标节点（find_path_to_node）
        - 否则 target_page_id：在拓扑地图上寻路到目标页面（find_path_to_page）
        - 节点寻路失败且存在目标页面时，降级为页面寻路
        """
        # 1) 目标节点优先（工作流图寻路）
        if target_node_id:
            result = context.find_path_to_node(target_node_id, target_task_id)
            if result.success:
                return result
            # 节点寻路失败：若有目标页面则降级，否则直接返回失败结果
            if target_page_id:
                context.log(f'[smart_jump] 节点寻路失败({result.reason})，降级为页面寻路: {target_page_id}', 'warning')
            else:
                return result

        # 2) 目标页面寻路（拓扑地图寻路）
        if target_page_id:
            return context.find_path_to_page(target_page_id)

        # 理论上不会走到这里（入口已校验）
        return PathResult(False, reason='未指定 target_page_id 或 target_node_id')

    # ========== 辅助 ==========

    def _clear_obstacles(self, context):
        """
        简化实现：尝试清理常见弹窗阻碍
        实际场景中可调用通用弹窗清理器或预定义的 close 弹窗任务组
        """
        context.log('[smart_jump] 尝试清理弹窗阻碍（简化实现，暂无操作）', 'info')

    @staticmethod
    def _resolve(value: Any, context) -> str:
        """解析 ${var} 模板字符串，None 安全"""
        if value is None:
            return ''
        return str(context.parse_expr(value))
