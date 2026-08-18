# core/executor.py
# P0 修复：无限循环崩溃、停止机制、线程安全日志
# P1 集成：图引擎（邻接表、环路检测、访问计数、迭代式跨任务跳转）
# 替换 StopIteration 为 FlowTermination 自定义异常

import logging
import re
import subprocess
import threading
import time
from datetime import datetime
from typing import Any

from core.graph.builder import AdjacencyGraph, GraphBuilder
from core.graph.pathfinder import PathFinder, PathResult
from core.models import Jump
from core.node_executors.base.smart_jump import SmartJumpNodeExecutor
from core.registry import NodeExecutorRegistry
from core.utils import resolve_template_string

logger = logging.getLogger(__name__)


class FlowTermination(Exception):
    """
    P1 新增：替代 StopIteration 的流程终止异常
    语义清晰：表示流程到达终点或被主动停止
    """

    pass


class GraphExecutor:
    """
    工业级图执行引擎
    P0 修复：无限循环、停止机制、线程安全
    P1 增强：邻接表预构建、环路检测、访问计数、迭代式跨任务跳转
    """

    # 单节点最大访问次数（防止环路死循环）
    MAX_NODE_VISITS = 50

    def __init__(self, project, project_dir=None, text_log_enabled=True, image_log_enabled=True, initial_context=None, debug_session=None):
        self.project = project
        self.tasks = project.tasks
        self.variables = project.variables.copy()
        self.current_task = None
        self.current_task_id = None
        self.current_node_index = 0
        self.current_node = None
        self.current_task_name = 'unknown'

        # 调试会话（断点/暂停/单步；None 时调试功能关闭，不影响正常执行）
        self.debug_session = debug_session

        # P0 修复：停止标志 + 线程锁
        self._stop = False
        self._stop_lock = threading.Lock()

        self.text_log_enabled = text_log_enabled
        self.image_log_enabled = image_log_enabled

        # P0 修复：线程安全日志列表（#7：条数上限，防 base64 图片日志撑爆内存）
        self._logs_lock = threading.Lock()
        self.logs: list[dict] = []
        self.max_logs = 500

        # 运行时状态
        self.is_emulator = False
        self.device_id = None
        self.android_width = None
        self.android_height = None
        self.window_hwnd = None
        self.window_rect = None
        self.project_dir = project_dir

        # P1 新增：图引擎数据
        self._graph_cache: dict[str, AdjacencyGraph] = {}
        self._topology_graph: AdjacencyGraph | None = None
        self._visited_count: dict[str, int] = {}  # 节点访问计数器
        self._call_stack: list[dict] = []  # 迭代式跨任务调用栈

        # 图像匹配得分（branch 择优用）
        self.last_match_score = 0.0

        # 内存模板（DRM 模式）
        self._memory_templates: dict[str, Any] = {}

        # 预构建邻接表
        self._build_graphs()

        if initial_context:
            self._apply_context(initial_context)

    def _build_graphs(self):
        """P1 新增：预构建所有任务组的邻接表"""
        try:
            self._graph_cache = GraphBuilder.build_from_project(self.project)
            topology = getattr(self.project, 'topology', None)
            if topology and topology.tasks:
                self._topology_graph = GraphBuilder.build_topology_graph(topology)
        except Exception as e:
            logger.warning(f'邻接表构建失败，降级为线性执行: {e}')
            self._graph_cache = {}

    # ========== P0 修复：停止机制 ==========

    def stop(self):
        """P0 修复：外部可调用的停止方法"""
        with self._stop_lock:
            self._stop = True
        self.log('🛑 [Executor] 收到停止信号，正在安全终止流程...', 'warning')

    @property
    def is_stopped(self) -> bool:
        with self._stop_lock:
            return self._stop

    # ========== P0 修复：线程安全日志 ==========

    def parse_expr(self, text: Any) -> Any:
        return resolve_template_string(text, self)

    def log(self, msg, level='info', image=None):
        resolved_msg = resolve_template_string(str(msg), self)
        now_str = datetime.now().strftime('%H:%M:%S')

        log_item = {'time': now_str, 'message': resolved_msg, 'level': level, 'image': image}

        # P0 修复：线程安全写入；⚡ 条数上限（保留最近 max_logs 条，防止长任务无限增长）
        with self._logs_lock:
            self.logs.append(log_item)
            if len(self.logs) > self.max_logs:
                del self.logs[: len(self.logs) - self.max_logs]

        prefix = f'[{level.upper()}]'
        print(f'{now_str} - {prefix} - {resolved_msg}')

        if level == 'error':
            logger.error(resolved_msg)
        elif level == 'warning':
            logger.warning(resolved_msg)
        else:
            logger.info(resolved_msg)

    # ========== 主执行入口 ==========

    def run(self, entry_task_id='main_task', start_node_id=None):
        """主执行入口"""
        self.log(
            f'🚀 [Executor] 启动图执行引擎 | 目标任务: {entry_task_id} | 起始节点: {start_node_id or "第一个节点"}'
        )

        try:
            self._execute_task_iterative(entry_task_id, start_node_id)
        except FlowTermination:
            if self.is_stopped:
                self.log('🛑 [Executor] 流程已被用户主动停止')
            else:
                self.log('🏁 [Executor] 当前分支连线到达终点，流程顺利结束')
        except Exception as e:
            self.log(f'💥 [Executor] 发生未处理系统级异常: {e}', 'error')
            raise

    def _execute_task_iterative(self, task_id, start_node_id=None):
        """
        P1 改造：迭代式任务执行（替代递归，防止栈溢出）
        使用显式调用栈管理跨任务跳转
        """
        # 初始调用栈帧
        initial_frame = {'task_id': task_id, 'start_node_id': start_node_id, 'return_on_complete': False}
        self._call_stack.append(initial_frame)

        while self._call_stack and not self.is_stopped:
            frame = self._call_stack[-1]
            task_id = frame['task_id']
            start_node_id = frame.get('start_node_id')

            # 执行当前帧的任务
            should_return = self._execute_single_task(task_id, start_node_id)

            # 弹出当前帧
            self._call_stack.pop()

            if should_return or not self._call_stack:
                # 需要返回到上一个任务组，或调用栈已空
                continue

            # 检查是否有新的帧需要执行（由 _handle_jump 添加）
            # 如果 _handle_jump 添加了新帧，循环会继续处理

    def _execute_single_task(self, task_id, start_node_id=None) -> bool:
        """
        执行单个任务组内的所有节点
        :return: True 表示应该返回到调用者
        """
        task = self.tasks.get(task_id)
        if not task:
            self.log(f'❌ 任务不存在: {task_id}', 'error')
            raise ValueError(f'任务不存在: {task_id}')

        self.current_task = task
        self.current_task_id = task_id
        self.current_task_name = task.task_name or task_id

        # 构建节点 ID -> 索引映射（O(1) 查找，替代 list.index()）
        node_id_to_index = {}
        for i, n in enumerate(task.nodes):
            node_id_to_index[n.node_id] = i

        if start_node_id:
            idx = node_id_to_index.get(start_node_id, 0)
            self.current_node_index = idx
        else:
            self.current_node_index = 0

        node_count = len(task.nodes)
        self.log(f'📋 [Task] 进入任务 [{task.task_name}] | 总节点数: {node_count}')

        while self.current_node_index < node_count and not self.is_stopped:
            node = task.nodes[self.current_node_index]

            if not node.enabled:
                self.log(f'⏸️ [Node] 节点 [{node.node_name}] (ID: {node.node_id}) 已禁用，自动跳过', 'warning')
                self.current_node_index += 1
                continue

            # P1 新增：访问计数 + 环路检测
            visit_count = self._visited_count.get(node.node_id, 0)
            if visit_count >= self.MAX_NODE_VISITS:
                self.log(
                    f'🔄 [环路保护] 节点 [{node.node_name}] 已被访问 {visit_count} 次，'
                    f'超过上限 {self.MAX_NODE_VISITS}，触发环路保护终止',
                    'error',
                )
                raise FlowTermination('环路保护触发')

            self._visited_count[node.node_id] = visit_count + 1

            # 调试检查点：断点命中/手动暂停/单步时阻塞，等待恢复信号
            if self.debug_session is not None:
                self.debug_session.on_node_enter(node.node_id, task_id)
                if self.is_stopped:
                    break

            # 执行节点
            result = self._execute_node_safely(node)

            # smart_jump 路径执行：节点成功后若写入了跳转路径，沿路径执行
            # （逐节点执行操作 / 页面确认，每步监测位置，偏离时从当前位置重新寻路）
            if result.get('success', True) and self.variables.get(SmartJumpNodeExecutor.PATH_VAR_KEY):
                path_ok = self._execute_smart_jump_path()
                if not path_ok:
                    # 跳转失败：视同节点失败，走失败路由（failure 连线或 on_failure）
                    result = {'success': False, 'error': '智能跳转执行失败'}

            # 路由决策：执行器显式 jump > branch 分支索引（图出边 branch_N）>
            # 成功/失败图出边（success/failure）> 旧数据 params 回退（迁移前 JSON 仍可运行）
            jump = None
            is_success = result.get('success', True)

            if 'jump' in result and result['jump']:
                jump = Jump.from_dict(result['jump'])
            else:
                graph = self._graph_cache.get(task_id)
                out_edges = graph.get_out_edges(node.node_id) if graph else []
                branch_index = result.get('branch_index')

                def _edge_jump(port):
                    for (tgt_node, tgt_task, edge_data) in out_edges:
                        if edge_data.get('source_port') == port and tgt_node:
                            return Jump(
                                target=tgt_task,
                                target_node=tgt_node,
                                return_on_complete=bool(edge_data.get('return_on_complete', False)),
                            )
                    return None

                if branch_index is not None:
                    # branch 命中：目标由分支连线 branch_N 决定（旧数据经 result['jump'] 已提前返回）
                    jump = _edge_jump(f'branch_{branch_index}')
                elif not is_success:
                    jump = _edge_jump('failure') or Jump.from_dict((node.params or {}).get('on_failure'))
                else:
                    jump = _edge_jump('success') or Jump.from_dict((node.params or {}).get('on_success'))

            # 处理跳转
            should_return = self._handle_jump(jump, node_id_to_index)
            if should_return:
                return True

        return False

    def _execute_node_safely(self, node):
        """沙箱执行节点，捕获异常"""
        try:
            return self._execute_node(node)
        except Exception as err:
            self.log(f'💥 [Sandbox 异常捕获] 节点 [{node.node_name}] 执行崩溃: {str(err)}', level='error')
            failure_jump = Jump.from_dict((node.params or {}).get('on_failure'))
            return {'success': False, 'error': str(err), 'jump': failure_jump.to_dict() if failure_jump else None}

    def _execute_node(self, node):
        """执行单个节点"""
        executor_class = NodeExecutorRegistry.get(node.node_type)
        if not executor_class:
            self.log(f'❌ [Node] 未找到节点类型对应的执行器: {node.node_type}', 'error')
            return {'success': False, 'error': 'executor not found'}

        executor = executor_class()

        if node.delay_before > 0:
            self.log(f'⏱️ [Node] 前置延迟: {node.delay_before} ms')
            time.sleep(node.delay_before / 1000.0)

        # P0 修复：无限循环崩溃
        # 旧代码: loop_count = node.loop_count if node.loop_count != -1 else float('inf')
        #         for i in range(int(loop_count)):  ← int(float('inf')) 抛 OverflowError
        # 新代码: 使用 while True 替代
        is_infinite = node.loop_count == -1
        loop_limit = node.loop_count if not is_infinite else 1
        result = None

        self.current_node = node
        self.current_task_name = self.current_task.task_name if self.current_task else 'unknown'

        self.log(f'▶️ [Node 执行] [{node.node_name}] ({node.node_type})')
        start_time = time.time()

        if is_infinite:
            # P0 修复：无限循环使用 while True
            while not self.is_stopped:
                try:
                    result = executor.execute(node, self)
                except Exception as e:
                    result = {'success': False, 'error': str(e)}

                # 无限循环模式下，失败才退出
                if not result.get('success'):
                    break
                # 成功后检查是否需要跳转
                if result.get('jump'):
                    break
        else:
            for _ in range(loop_limit):
                if self.is_stopped:
                    break
                try:
                    result = executor.execute(node, self)
                except Exception as e:
                    result = {'success': False, 'error': str(e)}

                if result.get('success'):
                    break
                if not result.get('success'):
                    break

        elapsed = (time.time() - start_time) * 1000
        status_str = '✅ 成功' if result and result.get('success') else '❌ 失败'
        self.log(f'⏹️ [Node 完成] {status_str} | 耗时: {elapsed:.2f}ms')

        return result or {'success': False}

    # ========== P1 改造：图驱动路由处理器 ==========

    def _handle_jump(self, jump: Jump | None, node_id_to_index: dict) -> bool:
        """
        P1 改造：图驱动路由处理器
        :return: True 表示需要返回到调用者（跨任务跳转完成或流程终止）
        """
        # 规则 1：无 Jump 或未指定 target_node -> 流程终点
        if not jump or not jump.target_node:
            self.log('🏁 [Flow 终点] 当前输出端口未连线，分支流程自然结束')
            raise FlowTermination('自然终点')

        self.log(f'🔀 [Jump 连线路由] ➔ 目标节点: {jump.target_node} (任务组: {jump.target or "当前组"})')

        # 规则 2：跨任务组连线跳转 -> 迭代式（添加调用栈帧，不再递归）
        if jump.target and jump.target != self.current_task_id:
            # P1 改造：迭代式跨任务跳转，将新任务压入调用栈
            self._call_stack.append(
                {
                    'task_id': jump.target,
                    'start_node_id': jump.target_node,
                    'return_on_complete': jump.return_on_complete,
                }
            )
            # 返回 True 让 _execute_single_task 退出，主循环会处理新帧
            return True

        # 规则 3：同任务组精准节点跳转（O(1) 查找，替代 list.index()）
        target_idx = node_id_to_index.get(jump.target_node)
        if target_idx is not None:
            self.current_node_index = target_idx
        else:
            self.log(f'❌ 找不到连线指向的目标节点 [{jump.target_node}]，流程终止', 'error')
            raise FlowTermination(f'目标节点不存在: {jump.target_node}')

        return False

    # ========== P1 新增：smart_jump 寻路接口 ==========

    def find_path_to_page(self, target_page_id: str) -> PathResult:
        """
        P1 新增：在拓扑地图上寻找从当前页面到目标页面的最短路径
        供 smart_jump 节点执行器调用
        """
        if not self._topology_graph:
            return PathResult(False, reason='拓扑地图未构建')

        # 获取当前页面 ID（从变量中读取）
        current_page = self.variables.get('current_page_id', '')
        if not current_page:
            return PathResult(False, reason='当前页面 ID 未知')

        return PathFinder.find_shortest_path(self._topology_graph, current_page, target_page_id)

    def find_path_to_node(self, target_node_id: str, task_id: str = None) -> PathResult:
        """
        P1 新增：在工作流图上寻找从当前节点到目标节点的最短路径
        供 smart_jump 节点执行器调用
        """
        task_id = task_id or self.current_task_id
        if not task_id or task_id not in self._graph_cache:
            return PathResult(False, reason=f'任务组 {task_id} 的邻接表不存在')

        graph = self._graph_cache[task_id]
        current_node_id = self.current_node.node_id if self.current_node else None
        if not current_node_id:
            return PathResult(False, reason='当前节点 ID 未知')

        return PathFinder.find_shortest_path(graph, current_node_id, target_node_id)

    def get_adjacency_graph(self, task_id: str = None) -> AdjacencyGraph | None:
        """获取指定任务组的邻接表"""
        task_id = task_id or self.current_task_id
        return self._graph_cache.get(task_id)

    def get_topology_graph(self) -> AdjacencyGraph | None:
        """获取拓扑地图邻接表"""
        return self._topology_graph

    # ========== P3 新增：smart_jump 路径执行（当前页判定 + 沿途执行 + 每步位置监测） ==========

    def _build_topology_index(self) -> tuple[dict[str, Any], list[Any]]:
        """
        拓扑索引（懒构建）：拓扑键（页面键 = page_id、操作键 = node_id）→ Node 映射
        + page_state 节点列表（现场评估当前页用）
        """
        if getattr(self, '_topology_index', None) is not None:
            return self._topology_index
        node_map: dict[str, Any] = {}
        pages: list[Any] = []
        topo = getattr(self.project, 'topology', None)
        if topo is not None:
            for node in topo.iter_nodes():
                key = topo.node_page_id(node) or node.node_id
                node_map[key] = node
                if node.node_type == 'page_state':
                    pages.append(node)
        self._topology_index = (node_map, pages)
        return self._topology_index

    def evaluate_current_page(self) -> str:
        """
        现场评估当前所在页面：依次执行拓扑中所有 page_state 节点的特征匹配，
        首个命中（success）即当前页；全部未命中返回空串。
        匹配成功时 page_state 执行器会顺带写入 current_page_id。
        """
        _, pages = self._build_topology_index()
        if not pages:
            return ''
        from core.node_executors.base.page_state import PageStateNodeExecutor

        evaluator = PageStateNodeExecutor()
        for page_node in pages:
            try:
                result = evaluator.execute(page_node, self)
            except Exception as e:
                self.log(f'[smart_jump] 页面评估异常 [{page_node.node_name}]: {e}', 'warning')
                result = {'success': False}
            if result.get('success'):
                return (page_node.params or {}).get('page_id', '')
        return ''

    def _resolve_current_page(self) -> str:
        """读取 / 评估当前位置：变量优先，缺失时现场评估并写回变量"""
        current = self.variables.get('current_page_id', '')
        if not current:
            current = self.evaluate_current_page()
            if current:
                self.variables['current_page_id'] = current
        return current

    def _execute_smart_jump_path(self) -> bool:
        """
        执行 smart_jump 记录的路径（由 smart_jump 执行器写入 __smart_jump_path__）。
        流程（每轮尝试）：
          确定当前位置 → BFS 寻路 → 逐节点执行（操作真实执行、页面识别确认）→
          每步后重新评估位置：已到达目标页 = 成功；
          位置偏离路径（用户手操 / 识别漂移）= 从新位置重新寻路；
          无路可达 / 超时 / 重试用尽 = 失败（调用方走失败路由）。
        """
        path_info = self.variables.get(SmartJumpNodeExecutor.PATH_VAR_KEY)
        if not path_info:
            return True
        target = path_info.get('target_page_id', '')
        timeout = max(100, int(path_info.get('timeout', 3000) or 3000))
        deadline = time.time() + timeout / 1000.0
        node_map, _ = self._build_topology_index()
        max_attempts = 3

        self.log(f'[smart_jump] 开始执行跳转 | 目标页面={target} 超时={timeout}ms')

        for attempt in range(1, max_attempts + 1):
            if self.is_stopped:
                self.log('[smart_jump] 收到停止信号，终止跳转', 'warning')
                break
            if time.time() >= deadline:
                self.log('[smart_jump] 跳转超时（超过超时时间上限）', 'error')
                break

            # 时刻监测位置：现场识别当前页（识别失败时回退变量缓存）
            current = self.evaluate_current_page()
            if not current:
                current = self.variables.get('current_page_id', '')
            elif current:
                self.variables['current_page_id'] = current
            if current == target:
                self.log(f'[smart_jump] 已在目标页面 [{target}]')
                self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
                return True
            if not current:
                self.log('[smart_jump] 无法确定当前位置，跳转失败', 'warning')
                break

            path_result = self.find_path_to_page(target)
            if not path_result.success or len(path_result.path) < 2:
                self.log(
                    f'[smart_jump] 第 {attempt} 次尝试：从 [{current}] 无路可达目标 [{target}]'
                    f'（{path_result.reason or "路径为空"}）',
                    'warning',
                )
                if attempt < max_attempts:
                    time.sleep(0.5)
                continue

            self.log(f'[smart_jump] 第 {attempt} 次尝试路径: {" → ".join(path_result.path)}')
            outcome = self._execute_topology_steps(path_result.path[1:], node_map, target, deadline)
            if outcome is True:
                self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
                self.log(f'[smart_jump] 跳转成功，已到达 [{target}]')
                return True
            if outcome == 'reroute':
                # 位置偏离路径预期（用户手操 / 识别漂移）→ 下一轮从新位置重新寻路
                self.log('[smart_jump] 位置偏离路径预期，从当前位置重新寻路', 'warning')
                continue
            # 路径执行失败（节点失败 / 路径耗尽未到达）→ 重试
            self.log('[smart_jump] 路径执行未到达目标，准备重试', 'warning')
            if attempt < max_attempts:
                time.sleep(0.5)

        self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
        self.log('[smart_jump] 跳转失败（超时 / 无路可达 / 重试用尽）', 'error')
        return False

    def _execute_topology_steps(self, steps, node_map, target, deadline) -> bool | str:
        """
        逐节点执行路径（不含起点，steps 为拓扑键序列）。
        - 操作节点（click/image_recognition/wait 等）：真实执行并播报日志
        - page_state 节点：执行页面确认（更新 current_page_id）
        - 每步后重新评估位置：
            到达目标页 → True；
            位置推进到路径中更靠后的页面（操作生效 / 手操）→ 从该页继续；
            当前位置不在路径中（手操到别处 / 识别漂移）→ 'reroute'（外层重新寻路）
        - 节点执行失败 / 路径耗尽未到达 → False
        """
        remaining = list(steps)
        # 路径中所有页面键（用于位置推进判断）
        page_keys = [k for k in steps if k in node_map and node_map[k].node_type == 'page_state']

        while remaining:
            if self.is_stopped:
                return False
            if time.time() >= deadline:
                self.log('[smart_jump] 路径执行超时', 'warning')
                return False

            key = remaining.pop(0)
            node = node_map.get(key)
            if node is None:
                self.log(f'[smart_jump] 路径节点 [{key}] 无法解析', 'warning')
                return False

            result = self._execute_node_safely(node)
            ok = result.get('success', True)
            self.log(f'[smart_jump] 路径节点 [{node.node_name}] ({node.node_type}) 执行{"成功" if ok else "失败"}')
            if not ok:
                self.log(f'[smart_jump] 路径节点执行失败: {result.get("error", "")}', 'error')
                return False

            # 每步后现场识别当前位置（时刻监测位置：用户手操 / 识别漂移立即感知；
            # 识别失败时回退变量缓存，避免误判偏离）
            current = self.evaluate_current_page()
            if not current:
                current = self.variables.get('current_page_id', '')
            elif current:
                self.variables['current_page_id'] = current
            if current == target:
                self.log(f'[smart_jump] 位置确认：已到达目标页面 [{target}]')
                return True
            if current:
                if current in page_keys:
                    pos = page_keys.index(current)
                    if pos > 0:
                        # 位置已推进到更靠后的页面：跳过该页之前的中间步骤
                        try:
                            skip = remaining.index(current)
                        except ValueError:
                            skip = 0
                        if skip > 0:
                            self.log(f'[smart_jump] 位置推进至 [{current}]，跳过 {skip} 个中间步骤')
                            remaining = remaining[skip:]
                        page_keys = page_keys[pos:]
                    continue
                # 当前位置不在路径中（用户手操到别处 / 识别漂移）→ 重新寻路
                self.log(f'[smart_jump] 当前位置 [{current}] 不在路径中，需重新寻路')
                return 'reroute'

        # 路径执行完毕：最后现场确认一次位置（识别失败时回退变量）
        current = self.evaluate_current_page()
        if not current:
            current = self.variables.get('current_page_id', '')
        if current == target:
            return True
        self.log(f'[smart_jump] 路径执行完毕但未确认到达目标页（当前 {current or "未知"}）', 'warning')
        return False

    # ========== 窗口与上下文管理（保持原有逻辑） ==========

    def get_window_rect(self):
        if self.window_rect is not None:
            return self.window_rect
        import pyautogui

        w, h = pyautogui.size()
        return (0, 0, w, h)

    def is_window_mode(self):
        return self.window_rect is not None

    def _apply_context(self, context):
        window_title = context.get('window_title') or context.get('windowTitle', '')
        if not window_title:
            self.log('ℹ️ [Footer 预热] 当前为全桌面模式，无需预热窗口')
            return

        self.log(f'🔍 [Footer 预热] 寻找目标工作窗口: [{window_title}]')

        try:
            import win32con
            import win32gui
        except ImportError:
            self.log('⚠️ [Footer 预热] win32gui 不可用，跳过窗口预热', 'warning')
            return

        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            self.log(f'⚠️ [Footer 预热] 未能找到指定窗口: [{window_title}]', 'warning')
            return

        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            self.log(f'✅ [Footer 预热] 窗口已自动激活置顶: {window_title}')
        except Exception:
            pass

        offset_top = context.get('offset_top') or context.get('offsetTop', 0)
        offset_bottom = context.get('offset_bottom') or context.get('offsetBottom', 0)
        offset_left = context.get('offset_left') or context.get('offsetLeft', 0)
        offset_right = context.get('offset_right') or context.get('offsetRight', 0)

        target_w = context.get('target_content_width') or context.get('targetContentWidth', 0)
        target_h = context.get('target_content_height') or context.get('targetContentHeight', 0)

        if target_w > 0 and target_h > 0:
            self.log(f'📏 [Footer 预热] 执行窗口 Resize: {target_w}x{target_h}')
            try:
                window_rect = win32gui.GetWindowRect(hwnd)
                pos_x, pos_y = window_rect[0], window_rect[1]

                cur_client_rect = win32gui.GetClientRect(hwnd)
                cur_window_rect = win32gui.GetWindowRect(hwnd)
                border_w = (cur_window_rect[2] - cur_window_rect[0]) - cur_client_rect[2]
                border_h = (cur_window_rect[3] - cur_window_rect[1]) - cur_client_rect[3]

                client_w = target_w + offset_left + offset_right
                client_h = target_h + offset_top + offset_bottom

                outer_w = client_w + border_w
                outer_h = client_h + border_h

                win32gui.SetWindowPos(hwnd, None, pos_x, pos_y, outer_w, outer_h, win32con.SWP_NOZORDER)
                self.log(f'✅ [Footer 预热] Resize 成功: {outer_w}x{outer_h}')
            except Exception as e:
                self.log(f'⚠️ [Footer 预热] Resize 失败: {e}', 'warning')

        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

        new_left = left + offset_left
        new_top = top + offset_top
        new_width = (right - left) - offset_left - offset_right
        new_height = (bottom - top) - offset_top - offset_bottom

        if new_width > 0 and new_height > 0:
            self.window_hwnd = hwnd
            self.window_rect = (new_left, new_top, new_width, new_height)
            self.variables['window_content_offset'] = {
                'top': offset_top,
                'bottom': offset_bottom,
                'left': offset_left,
                'right': offset_right,
            }
            self.variables['window_rect'] = self.window_rect
            self.log(f'🎯 [Footer 预热] 挂载全局工作坐标区: {self.window_rect}')

        self.is_emulator = context.get('is_emulator') or context.get('isEmulator', False)
        if self.is_emulator:
            device_id = self._auto_detect_device(window_title)
            if device_id:
                self.device_id = device_id
                android_w, android_h = self._get_android_resolution(device_id)
                if android_w and android_h:
                    self.android_width = android_w
                    self.android_height = android_h
                    self.variables['android_width'] = android_w
                    self.variables['android_height'] = android_h
                    self.log(f'🤖 [Footer 预热] 模拟器 ADB 绑定成功: {device_id} ({android_w}x{android_h})')
                else:
                    self.log(f'⚠️ [Footer 预热] 无法获取 ADB 分辨率: {device_id}', 'warning')
            else:
                self.log('⚠️ [Footer 预热] 未找到 ADB 设备，自动回退为 PC 点击', 'warning')
                self.is_emulator = False

    def _auto_detect_device(self, title):
        match = re.search(r'(\d{4,5})$', title)
        if match:
            port = match.group(1)
            candidates = [f'127.0.0.1:{port}', f'emulator-{port}']
            for candidate in candidates:
                if self._check_device(candidate):
                    return candidate
        devices = self._get_adb_devices()
        return devices[0] if devices else None

    def _check_device(self, device_id):
        try:
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell', 'echo', 'test'], capture_output=True, text=True, timeout=2
            )
            return result.returncode == 0 and 'test' in result.stdout
        except Exception:
            return False

    def _get_adb_devices(self):
        try:
            result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=3)
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if 'device' in line and 'offline' not in line:
                    devices.append(line.split()[0])
            return devices
        except Exception:
            return []

    def _get_android_resolution(self, device_id):
        try:
            cmd = ['adb', '-s', device_id, 'shell', 'wm', 'size']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None, None
        except Exception:
            return None, None
