# core/executor.py
# P0 修复：无限循环崩溃、停止机制、线程安全日志
# P1 集成：图引擎（邻接表、环路检测、访问计数、迭代式跨任务跳转）
# 替换 StopIteration 为 FlowTermination 自定义异常

import logging
import re
import subprocess
import threading
import time
from dataclasses import replace
from datetime import datetime
from typing import Any

from core.graph.builder import AdjacencyGraph, GraphBuilder
from core.graph.pathfinder import PathFinder, PathResult
from core.models import Jump, TopologyMap
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


class TaskIterationComplete(Exception):
    """当前流程的一次执行自然到达未连线出口。"""

    def __init__(self, message='自然终点', success=True):
        super().__init__(message)
        self.success = bool(success)


class TaskExecutionFailed(RuntimeError):
    """节点按业务语义返回失败，而不是执行器发生未处理崩溃。"""

    pass


class GraphExecutor:
    """
    工业级图执行引擎
    P0 修复：无限循环、停止机制、线程安全
    P1 增强：邻接表预构建、环路检测、访问计数、迭代式跨任务跳转
    """

    # 只有真正读取或操控界面的节点才需要在执行前检查弹窗。
    # branch / logic_check 需按内部条件动态判断，不能把纯变量条件误判为屏幕操作。
    _DIRECT_UI_NODE_TYPES = frozenset(
    {'click', 'scroll', 'drag', 'text_input', 'control', 'image_recognition', 'ocr_recognition', 'page_state', 'smart_jump'}
    )
    _UI_CONDITION_TYPES = frozenset({'image_exists', 'text_contains', 'control_exists'})

    # 单节点最大访问次数（防止环路死循环）
    MAX_NODE_VISITS = 50

    def __init__(self, project, project_dir=None, text_log_enabled=True, image_log_enabled=True, initial_context=None, debug_session=None):
        self.project = project
        self.tasks = project.tasks
        self.variables = project.variables.copy()
        self._context_keys: set[str] = set()
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

        # ⚡ 项目级引擎设置（前端「项目设置」页面配置，project.json 的 settings 段）
        self.settings: dict[str, Any] = dict(getattr(project, 'settings', {}) or {})
        self.max_logs = int(self.settings.get('max_logs', 500))
        self.MAX_NODE_VISITS = int(self.settings.get('max_node_visits', 50))

        # P0 修复：线程安全日志列表（#7：条数上限，防 base64 图片日志撑爆内存）
        self._logs_lock = threading.Lock()
        self.logs: list[dict] = []

        # 运行时状态
        self.is_emulator = False
        self.is_android_target = False
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
        self._call_stack: list[dict] = []  # 主图/函数显式调用栈
        self._active_frame: dict | None = None
        self.MAX_CALL_DEPTH = 32
        self.checkpoint_callback = None

        # ⚡ 弹窗处理（组名含「弹窗」的拓扑组为旁路）：弹窗子图 + 弹窗页列表 + 单步处理次数上限
        self._popup_graphs: dict[str, AdjacencyGraph] = {}
        self._popup_pages: list[tuple[str, Any]] = []  # (task_id, page_state_node)
        self._popup_handled_this_step = 0
        self.MAX_POPUP_HANDLES = int(self.settings.get('popup_max_handles', 5))  # 单步最大弹窗处理次数
        # ⚡ 弹窗防重复触发：同一弹窗关闭动作后的冷却窗口（项目响应延迟期间特征短暂残留，
        # 冷却窗口内不再重复点击；窗口过期后若仍在（关闭失败）才再次处理）
        self.POPUP_COOLDOWN_MS = int(self.settings.get('popup_cooldown_ms', 800))
        self._popup_last_handled: dict[str, float] = {}  # page_id → 上次执行关闭动作的时间戳(ms)
        # ⚡ 互弹死锁保护（跨检查点）：冷却使单次调用内最多处理 1 次，死锁体现在
        # 「连续多次检查点都在处理弹窗（关不完）」——连续计数超限即报错
        self._popup_consecutive_handles = 0
        self.MAX_POPUP_CONSECUTIVE = int(self.settings.get('popup_max_consecutive', 3))

        # ⚡ 每步共享工作区截图（弹窗检测 + 页面评估复用同一帧，减少截图开销）
        self._step_screen = None

        # ⚡ 加载等待（帧稳定检测 + 超时轮询）：页面跳转/加载期间不立即失败
        self._prev_frame = None  # 上一帧工作区截图（帧差比较）
        self._stable_frame_count = 0  # 连续静止帧计数

        # 图像匹配得分（branch 择优用）
        self.last_match_score = 0.0

        # 内存模板（DRM 模式）
        self._memory_templates: dict[str, Any] = {}

        # 预构建邻接表
        self._build_graphs()

        if initial_context:
            self._apply_context(initial_context)

    def get_setting(self, key: str, default=None):
        """读取项目级引擎设置（前端「项目设置」页面配置），缺失用 default"""
        return self.settings.get(key, default)

    def _build_graphs(self):
        """预构建所有流程的邻接表。"""
        try:
            self._graph_cache = GraphBuilder.build_from_project(self.project)
            topology = getattr(self.project, 'topology', None)
            if topology and topology.tasks:
                self._topology_graph = GraphBuilder.build_topology_graph(topology)
                self._build_popup_index(topology)
        except Exception as e:
            logger.warning(f'邻接表构建失败，降级为线性执行: {e}')
            self._graph_cache = {}

    # ========== 页面节点级高频随机弹窗旁路处理 ==========

    def _build_popup_index(self, topology):
        """构建弹窗关闭子图，但只监测显式勾选的页面节点。"""
        self._popup_graphs = GraphBuilder.build_popup_graphs(topology)
        pages: list[tuple[str, Any]] = []
        for task in topology.tasks:
            if not GraphBuilder.is_popup_task(task):
                continue
            graph = self._popup_graphs.get(task.task_id)
            if graph is None:
                continue
            explicit_pages = [node for node in task.nodes if GraphBuilder.is_popup_node(node)]
            pages.extend((task.task_id, node) for node in explicit_pages)
        self._popup_pages = pages
        if pages:
            labels = ', '.join(node.node_name or node.node_id for _, node in pages)
            self.log(
                f' [弹窗处理] 已启用高频随机弹窗页面: {labels}'
                '（仅在界面识别/操作节点执行前检测）'
            )

    @classmethod
    def _node_requires_popup_check(cls, node) -> bool:
        """节点是否即将读取或操控目标界面。"""
        node_type = str(getattr(node, 'node_type', '') or '')
        if node_type in cls._DIRECT_UI_NODE_TYPES:
            return True
        if node_type not in {'branch', 'logic_check'}:
            return False

        def contains_ui_condition(value) -> bool:
            if isinstance(value, dict):
                condition_type = value.get('condition_type') or value.get('type')
                if condition_type in cls._UI_CONDITION_TYPES:
                    return True
                return any(contains_ui_condition(item) for item in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_ui_condition(item) for item in value)
            return False

        return contains_ui_condition(getattr(node, 'params', None) or {})

    def _capture_workspace_step(self) -> bool:
        """捕获与当前输入目标绑定的工作区帧；失败时严格返回 False。"""
        from core.services.runtime_target import capture_workspace

        try:
            self._step_screen = capture_workspace(self)
            self._ocr_frame_cache = None
            return True
        except Exception as exc:
            self._step_screen = None
            self._last_capture_error = str(exc)
            self.log(f' [目标截图] {exc}', 'error')
            return False

    def _drain_popups(self, deadline: float | None = None) -> dict[str, Any]:
        """阻塞式清理多层弹窗，只有稳定确认 CLEAR 才允许主流程继续。"""
        if not getattr(self, '_popup_pages', None):
            return {'status': 'clear', 'handled_count': 0}
        if self.is_stopped:
            return {'status': 'error', 'handled_count': 0, 'error': '执行已停止'}

        from core.node_executors.base.page_state import PageStateNodeExecutor

        now = time.time()
        local_deadline = now + max(500, int(self.get_setting('popup_total_timeout_ms', 5000))) / 1000.0
        deadline = min(local_deadline, deadline) if deadline is not None else local_deadline
        poll_s = max(0.03, int(self.get_setting('popup_poll_ms', 150)) / 1000.0)
        quiet_frames_required = max(1, int(self.get_setting('popup_quiet_frames', 2)))
        quiet_window_s = max(0, int(self.get_setting('popup_quiet_window_ms', 500))) / 1000.0
        evaluator = PageStateNodeExecutor()
        saved_current = self.variables.get('current_page_id', '')
        handled_count = 0
        quiet_frames = 0
        quiet_started = None
        self._prev_frame = None

        try:
            while time.time() < deadline and not self.is_stopped:
                if not self._capture_workspace_step():
                    return {
                        'status': 'error',
                        'handled_count': handled_count,
                        'error': getattr(self, '_last_capture_error', '工作区截图失败'),
                    }

                now_ms = time.time() * 1000
                hit = None
                cooling_matches = []
                for task_id, page_node in self._popup_pages:
                    try:
                        result = evaluator.execute(page_node, self)
                    except Exception as exc:
                        return {
                            'status': 'error',
                            'handled_count': handled_count,
                            'error': f'弹窗页评估异常 [{page_node.node_name}]: {exc}',
                        }
                    if not result.get('success'):
                        continue
                    page_id = TopologyMap.node_page_id(page_node) or page_node.node_id
                    elapsed_ms = now_ms - self._popup_last_handled.get(page_id, 0.0)
                    if elapsed_ms < self.POPUP_COOLDOWN_MS:
                        cooling_matches.append((page_id, max(0, int(elapsed_ms))))
                        continue
                    hit = (task_id, page_node, page_id)
                    break

                if hit is not None:
                    if handled_count >= self.MAX_POPUP_HANDLES:
                        return {
                            'status': 'error',
                            'handled_count': handled_count,
                            'error': f'单次清场已达到 {self.MAX_POPUP_HANDLES} 次，弹窗仍未清除',
                        }
                    task_id, page_node, page_id = hit
                    label = self._topology_page_label(page_id)
                    self.log(f'🚨 [弹窗处理] 第 {handled_count + 1} 次：检测到 [{label}]，执行关闭流程')
                    close_result = self._execute_popup_close(task_id, page_node)
                    if not close_result.get('success'):
                        return {
                            'status': 'error',
                            'handled_count': handled_count,
                            'error': close_result.get('error', f'弹窗 [{label}] 关闭失败'),
                        }
                    handled_count += 1
                    self._popup_last_handled[page_id] = time.time() * 1000
                    quiet_frames = 0
                    quiet_started = None
                    self._prev_frame = None
                    time.sleep(poll_s)
                    continue

                if cooling_matches:
                    labels = ', '.join(
                        f'{self._topology_page_label(page_id)}({elapsed}ms)'
                        for page_id, elapsed in cooling_matches
                    )
                    self.log(f' [弹窗处理] 弹窗仍存在且处于冷却中: {labels}；保持阻塞')
                    quiet_frames = 0
                    quiet_started = None
                    time.sleep(poll_s)
                    continue

                if handled_count == 0:
                    self._popup_consecutive_handles = 0
                    return {'status': 'clear', 'handled_count': 0}

                if quiet_started is None:
                    quiet_started = time.time()
                if self._frame_is_stable():
                    quiet_frames += 1
                else:
                    quiet_frames = 0
                if quiet_frames >= quiet_frames_required and time.time() - quiet_started >= quiet_window_s:
                    self._popup_consecutive_handles = 0
                    self.log(
                        f' [弹窗处理] 清场完成：连续 {quiet_frames} 个稳定帧无弹窗，'
                        f'静默 {int((time.time() - quiet_started) * 1000)}ms'
                    )
                    return {'status': 'clear', 'handled_count': handled_count}
                time.sleep(poll_s)

            self._popup_consecutive_handles += 1
            return {
                'status': 'error',
                'handled_count': handled_count,
                'error': '弹窗清场超时：仍有弹窗、冷却残留或画面尚未稳定',
            }
        finally:
            self.variables['current_page_id'] = saved_current

    def _ensure_popups_clear(self, deadline: float | None = None) -> bool:
        self._last_popup_result = self._drain_popups(deadline)
        if self._last_popup_result.get('status') == 'clear':
            return True
        self.log(f' [弹窗处理] {self._last_popup_result.get("error", "清场失败")}', 'error')
        return False

    def _execute_popup_close(self, task_id: str, page_node) -> dict[str, Any]:
        """
        执行弹窗关闭流程：从命中的弹窗页沿组内 success 边依次执行操作节点，
        直到组内无路可走（弹窗特征消失由外层循环复检）。
        """
        graph = self._popup_graphs.get(task_id)
        if graph is None:
            return {'success': False, 'error': f'弹窗组图不存在: {task_id}'}

        # 组内节点映射：page 键 → Node（含操作节点）
        task = None
        for t in getattr(self.project, 'topology', None).tasks if getattr(self.project, 'topology', None) else []:
            if t.task_id == task_id:
                task = t
                break
        if task is None:
            return {'success': False, 'error': f'弹窗任务不存在: {task_id}'}
        node_map: dict[str, Any] = {}
        for n in task.nodes:
            key = TopologyMap.node_page_id(n) or n.node_id
            node_map[key] = n

        current_key = TopologyMap.node_page_id(page_node) or page_node.node_id
        visited = set()
        steps = 0
        result = {'success': True}
        while current_key and steps < 20:
            if current_key in visited:
                return {'success': False, 'error': f'弹窗关闭流程存在环路: {current_key}'}
            visited.add(current_key)
            node = node_map.get(current_key)
            if node is None:
                return {'success': False, 'error': f'弹窗关闭节点无法解析: {current_key}'}
            steps += 1
            if node.node_type != 'page_state':
                self.log(f' [弹窗处理] 执行关闭动作: [{node.node_name}] ({node.node_type})')
                self._step_screen = None
                if self._node_requires_popup_check(node) and node.node_type in {'branch', 'logic_check', 'page_state'}:
                    if not self._capture_workspace_step():
                        return {'success': False, 'error': getattr(self, '_last_capture_error', '关闭流程截图失败')}
                result = self._execute_node_safely(node)
                self._step_screen = None
                if not result.get('success'):
                    return {'success': False, 'error': result.get('error') or f'关闭动作 [{node.node_name}] 失败'}

            edges = list(graph.get_out_edges(current_key))
            if not edges:
                return {'success': True}

            if result.get('branch_index') is not None:
                port = f'branch_{result["branch_index"]}'
                candidates = [edge for edge in edges if (edge[2] or {}).get('source_port') == port]
            elif node.node_type != 'page_state':
                port = 'success' if result.get('success', True) else 'failure'
                candidates = [edge for edge in edges if (edge[2] or {}).get('source_port') == port]
                if not candidates and len(edges) == 1:
                    candidates = edges
            else:
                candidates = edges

            if len(candidates) != 1:
                return {
                    'success': False,
                    'error': f'弹窗节点 [{node.node_name}] 存在 {len(edges)} 条出口但无法确定唯一分支，请配置条件端口',
                }
            next_key = candidates[0][0]
            current_key = next_key

        if steps >= 20:
            return {'success': False, 'error': '弹窗关闭流程超过20步安全上限'}
        return {'success': True}

    # ========== P0 修复：停止机制 ==========

    def stop(self):
        """P0 修复：外部可调用的停止方法"""
        with self._stop_lock:
            self._stop = True
        from core.services.runtime_session import close_runtime_sessions

        close_runtime_sessions(self)
        self.log(' [Executor] 收到停止信号，正在安全终止流程...', 'warning')

    @property
    def is_stopped(self) -> bool:
        with self._stop_lock:
            return self._stop

    # ========== P0 修复：线程安全日志 ==========

    def parse_expr(self, text: Any) -> Any:
        return resolve_template_string(text, self)

    def log(self, msg, level='info', image=None, category=None):
        from core.logging_model import infer_log_category

        resolved_msg = resolve_template_string(str(msg), self)
        now_str = datetime.now().strftime('%H:%M:%S')

        log_item = {
            'time': now_str,
            'message': resolved_msg,
            'level': level,
            'category': infer_log_category(resolved_msg, category),
            'image': image,
        }

        # P0 修复：线程安全写入；⚡ 条数上限（保留最近 max_logs 条，防止长任务无限增长）
        with self._logs_lock:
            self.logs.append(log_item)
            if len(self.logs) > self.max_logs:
                del self.logs[: len(self.logs) - self.max_logs]

        prefix = f'[{level.upper()}]'
        try:
            print(f'{now_str} - {prefix} - {resolved_msg}')
        except (UnicodeEncodeError, OSError, ValueError):
            # 标准输出只是开发期副本；前端日志列表和 logging 才是权威链路。
            # 某些 Windows 后台宿主仍会提供 GBK/失效句柄，不能因此终止脚本。
            pass

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
            f' [Executor] 启动图执行引擎 | 目标任务: {entry_task_id} | 起始节点: {start_node_id or "第一个节点"}'
        )

        try:
            self._execute_task_iterative(entry_task_id, start_node_id)
            if self.is_stopped:
                self.log(' [Executor] 流程已被用户主动停止')
            else:
                self.log(' [Executor] 当前分支连线到达终点，流程顺利结束')
        except FlowTermination:
            if self.is_stopped:
                self.log(' [Executor] 流程已被用户主动停止')
            else:
                self.log(' [Executor] 当前分支连线到达终点，流程顺利结束')
        except TaskExecutionFailed as exc:
            self.log(f' [Executor] 任务执行失败: {exc}', 'error')
            raise
        except Exception as e:
            self.log(f' [Executor] 发生未处理系统级异常: {e}', 'error')
            raise
        finally:
            from core.services.runtime_session import close_runtime_sessions

            close_runtime_sessions(self)

    def _execute_task_iterative(self, task_id, start_node_id=None):
        """显式栈流程调度：支持跨流程转移和可重复的参数化子流程调用。"""
        initial_frame = {
            'task_id': task_id,
            'frame_kind': 'main',
            'start_node_id': start_node_id,
            'entry_start_node_id': start_node_id,
            'repeat_count': 1,
            'repeat_index': 0,
            'repeat_interval_ms': 0,
            'iteration_started': False,
            'variables': self.variables,
            'call_depth': 0,
        }
        self._call_stack.append(initial_frame)

        while self._call_stack and not self.is_stopped:
            frame = self._call_stack[-1]
            self._active_frame = frame
            task_id = frame['task_id']
            start_node_id = frame.get('start_node_id')
            self.variables = frame.get('variables', self.variables)

            task = self.tasks.get(task_id)
            if not task:
                self.log(f' 任务不存在: {task_id}', 'error')
                raise ValueError(f'任务不存在: {task_id}')

            repeat_count = int(frame.get('repeat_count', 1) or 0)
            if repeat_count < -1:
                raise ValueError(f'流程 [{task.task_name or task_id}] 的调用次数无效: {repeat_count}')
            if repeat_count == 0:
                self.log(f'⏭️ [执行] 图 [{task.task_name or task_id}] 调用次数为 0，已跳过', 'warning')
                self._remove_frame(frame)
                continue

            if not frame.get('iteration_started'):
                for node in task.nodes:
                    self._visited_count.pop(node.node_id, None)
                frame['iteration_started'] = True

            iteration_success = True
            try:
                execution_state = self._execute_single_task(task_id, start_node_id)
            except TaskIterationComplete as complete:
                if frame.get('frame_kind') == 'function':
                    self.log(' [函数] 函数必须通过显式返回节点结束，不能从未连线出口隐式返回', 'error')
                    execution_state = 'function_return'
                    frame['function_result'] = {
                        'outcome_id': 'system_exception',
                        'outputs': {},
                        'error': '函数缺少显式返回路径',
                    }
                else:
                    execution_state = 'complete'
                    iteration_success = complete.success
            except Exception as exc:
                if frame.get('frame_kind') == 'function' and frame.get('return_to_frame') is not None:
                    self.log(f' [函数] [{task.task_name or task_id}] 运行异常: {exc}', 'error')
                    execution_state = 'function_return'
                    frame['function_result'] = {
                        'outcome_id': 'system_exception',
                        'outputs': {},
                        'error': str(exc),
                    }
                else:
                    raise

            if self.is_stopped:
                break

            if execution_state == 'call':
                continue

            if execution_state == 'function_return':
                self._remove_frame(frame)
                self._resume_function_caller(frame, frame.get('function_result') or {})
                continue

            if execution_state == 'transfer':
                self._remove_frame(frame)
                continue

            if not iteration_success:
                self._remove_frame(frame)
                raise TaskExecutionFailed(f'流程 [{task.task_name or task_id}] 执行失败')

            frame['repeat_index'] = int(frame.get('repeat_index', 0)) + 1
            is_infinite = repeat_count == -1
            if is_infinite or frame['repeat_index'] < repeat_count:
                interval_ms = max(0, int(frame.get('repeat_interval_ms', 0) or 0))
                self.log(
                    f'🔁 [执行] 图 [{task.task_name or task_id}] 完成第 {frame["repeat_index"]} 次，'
                    f'准备第 {frame["repeat_index"] + 1} 次执行'
                )
                if interval_ms:
                    time.sleep(interval_ms / 1000.0)
                frame['start_node_id'] = frame.get('entry_start_node_id')
                frame['iteration_started'] = False
                continue

            self._remove_frame(frame)

        self._active_frame = None

    def _remove_frame(self, frame):
        if self._call_stack and self._call_stack[-1] is frame:
            self._call_stack.pop()
            return
        try:
            self._call_stack.remove(frame)
        except ValueError:
            pass

    def _execute_single_task(self, task_id, start_node_id=None) -> str:
        """
        执行单个流程内的所有节点
        :return: complete / transfer / call
        """
        if self._active_frame and 'completion_pending' in self._active_frame:
            success = bool(self._active_frame.pop('completion_pending'))
            raise TaskIterationComplete('子流程返回后当前出口未连线', success=success)

        task = self.tasks.get(task_id)
        if not task:
            self.log(f' 任务不存在: {task_id}', 'error')
            raise ValueError(f'任务不存在: {task_id}')

        self.current_task = task
        self.current_task_id = task_id
        self.current_task_name = task.task_name or task_id

        # 构建节点 ID -> 索引映射（O(1) 查找，替代 list.index()）
        node_id_to_index = {}
        for i, n in enumerate(task.nodes):
            node_id_to_index[n.node_id] = i

        if start_node_id:
            if start_node_id not in node_id_to_index:
                raise ValueError(f'流程 [{task.task_name or task_id}] 中不存在起始节点: {start_node_id}')
            self.current_node_index = node_id_to_index[start_node_id]
        else:
            self.current_node_index = 0

        node_count = len(task.nodes)
        self.log(f' [Flow] 进入流程 [{task.task_name}] | 总节点数: {node_count}')

        while self.current_node_index < node_count and not self.is_stopped:
            node = task.nodes[self.current_node_index]

            if self.checkpoint_callback:
                try:
                    self.checkpoint_callback(task_id, node.node_id, dict(self.variables))
                except Exception as exc:
                    self.log(f' [恢复点] 保存失败: {exc}', 'warning')

            if not node.enabled:
                self.log(f' [Node] 节点 [{node.node_name}] (ID: {node.node_id}) 已禁用，自动跳过', 'warning')
                self.current_node_index += 1
                continue

            # P1 新增：访问计数 + 环路检测
            visit_count = self._visited_count.get(node.node_id, 0)
            if visit_count >= self.MAX_NODE_VISITS:
                self.log(
                    f' [环路保护] 节点 [{node.node_name}] 已被访问 {visit_count} 次，'
                    f'超过上限 {self.MAX_NODE_VISITS}，触发环路保护终止',
                    'error',
                )
                raise RuntimeError('环路保护触发')

            self._visited_count[node.node_id] = visit_count + 1

            # 调试检查点：断点命中/手动暂停/单步时阻塞，等待恢复信号
            if self.debug_session is not None:
                self.debug_session.on_node_enter(node.node_id, task_id)
                if self.is_stopped:
                    break

            # 弹窗只在真正读取/操控界面的节点前检查。日志、变量、等待、窗口设置、
            # 子流程调度等纯逻辑/准备节点不截图，也不扫描任何页面状态。
            if self._node_requires_popup_check(node):
                popup_clear = self._ensure_popups_clear()
                if self.is_stopped:
                    break
                if not popup_clear:
                    result = {'success': False, 'error': self._last_popup_result.get('error', '弹窗清场失败')}
                else:
                    result = self._execute_node_safely(node)
            else:
                result = self._execute_node_safely(node)

            # smart_jump 路径执行：节点成功后若写入了跳转路径，沿路径执行
            # （逐节点执行操作 / 页面确认，每步监测位置，偏离时从当前位置重新寻路）
            if result.get('success', True) and self.variables.get(SmartJumpNodeExecutor.PATH_VAR_KEY):
                path_ok = self._execute_smart_jump_path()
                if not path_ok:
                    # 跳转失败：视同节点失败，走 failure 连线。
                    result = {'success': False, 'error': '智能跳转执行失败'}

            graph = self._graph_cache.get(task_id)
            out_edges = graph.get_out_edges(node.node_id) if graph else []

            def _edge_jump(port, stable_port_id=None):
                for (tgt_node, tgt_task, edge_data) in out_edges:
                    edge_port_id = edge_data.get('source_port_id') or edge_data.get('source_port')
                    matches = edge_port_id == stable_port_id if stable_port_id else edge_data.get('source_port') == port
                    if matches and tgt_node:
                        return Jump(
                            target_task=tgt_task,
                            target_node=tgt_node,
                        )
                return None

            if result.get('success', True) and result.get('call_function'):
                try:
                    outcome_jumps = {}
                    for _target, _target_task, edge_data in out_edges:
                        stable_id = str(edge_data.get('source_port_id') or edge_data.get('source_port') or '')
                        if stable_id:
                            outcome_jumps[stable_id] = _edge_jump(str(edge_data.get('source_port') or ''), stable_id)
                    self._schedule_function_call(result['call_function'], outcome_jumps)
                    return 'call'
                except Exception as exc:
                    self.log(f' [调用函数] 无法启动函数: {exc}', 'error')
                    result = {'success': False, 'error': str(exc)}

            if result.get('success', True) and result.get('function_return'):
                if not self._active_frame or self._active_frame.get('frame_kind') != 'function':
                    result = {'success': False, 'error': '函数返回节点只能在函数画布中执行'}
                else:
                    self._active_frame['function_result'] = result['function_return']
                    return 'function_return'

            # 路由决策只读取实体边：分支使用稳定端口，其他节点使用成功/失败端口。
            jump = None
            is_success = result.get('success', True)
            branch_index = result.get('branch_index')
            branch_id = result.get('branch_id')

            if branch_index is not None:
                jump = _edge_jump(f'branch_{branch_index}', branch_id)
            elif not is_success:
                jump = _edge_jump('failure')
            else:
                jump = _edge_jump('success')

            # 处理跳转
            should_return = self._handle_jump(jump, node_id_to_index, is_success=is_success)
            if should_return:
                return 'transfer'

        return 'complete'

    def _execute_node_safely(self, node):
        """沙箱执行节点，捕获异常"""
        try:
            return self._execute_node(node)
        except Exception as err:
            self.log(f' [Sandbox 异常捕获] 节点 [{node.node_name}] 执行崩溃: {str(err)}', level='error')
            return {'success': False, 'error': str(err)}

    def _execute_node(self, node):
        """执行单个节点"""
        executor_class = NodeExecutorRegistry.get(node.node_type)
        if not executor_class:
            self.log(f' [Node] 未找到节点类型对应的执行器: {node.node_type}', 'error')
            return {'success': False, 'error': 'executor not found'}

        executor = executor_class()

        if node.delay_before > 0:
            self.log(f' [Node] 前置延迟: {node.delay_before} ms')
            time.sleep(node.delay_before / 1000.0)

        # P0 修复：无限循环崩溃
        # 旧代码: loop_count = node.loop_count if node.loop_count != -1 else float('inf')
        #         for i in range(int(loop_count)):  ← int(float('inf')) 抛 OverflowError
        # 新代码: 使用 while True 替代
        is_infinite = node.loop_count == -1
        loop_limit = max(0, int(node.loop_count)) if not is_infinite else 1
        result = None

        self.current_node = node
        self.current_task_name = self.current_task.task_name if self.current_task else 'unknown'

        self.log(f' [Node 执行] [{node.node_name}] ({node.node_type})')
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
                if result.get('call_function') or result.get('function_return'):
                    break
        else:
            if loop_limit == 0:
                result = {'success': True, 'skipped': True}
            for _ in range(loop_limit):
                if self.is_stopped:
                    break
                try:
                    result = executor.execute(node, self)
                except Exception as e:
                    result = {'success': False, 'error': str(e)}

                if not result.get('success'):
                    break
                # 函数调用必须立即交还给调用栈调度器。
                if result.get('call_function') or result.get('function_return'):
                    break

        elapsed = (time.time() - start_time) * 1000
        status_str = ' 成功' if result and result.get('success') else ' 失败'
        self.log(f' [Node 完成] {status_str} | 耗时: {elapsed:.2f}ms')
        if result and not result.get('success'):
            detail = str(result.get('error') or result.get('stop_reason') or '节点返回失败').strip()
            self.log(f' [Node 失败原因] [{node.node_name}] {detail}', 'error')
        if result and result.get('capture_tier'):
            input_result = result.get('input') if isinstance(result.get('input'), dict) else {}
            input_summary = ''
            if input_result:
                target_point = input_result.get('android_point') or input_result.get('screen_point')
                input_summary = (
                    f' | 输入={input_result.get("method", "unknown")}/'
                    f'{input_result.get("delivery", "unknown")}'
                )
                if target_point:
                    input_summary += f'@{target_point}'
            self.log(
                '[视觉性能] '
                f'采帧={result.get("capture_tier")} | '
                f'处理={result.get("processed_fps", 0)}fps | '
                f'帧龄P95={result.get("frame_age_p95_ms", 0)}ms | '
                f'匹配P95={result.get("match_p95_ms", 0)}ms | '
                f'点击={result.get("click_count", 0)} | '
                f'结束={result.get("stop_reason", "unknown")}'
                f'{input_summary}'
            )

        return result or {'success': False}

    def _schedule_function_call(self, call: dict, outcome_jumps: dict[str, Jump | None]):
        caller = self._active_frame
        if caller is None:
            raise RuntimeError('函数调用栈状态无效')
        function_id = str(call.get('function_id') or '').strip()
        if not function_id:
            raise ValueError('未选择目标函数')
        target = self.tasks.get(function_id)
        if target is None or str(getattr(target, 'role', '')) != 'function':
            raise ValueError(f'目标函数不存在: {function_id}')
        active_function_ids = {
            str(frame.get('task_id') or '')
            for frame in self._call_stack
            if frame.get('frame_kind') == 'function'
        }
        if function_id in active_function_ids:
            raise ValueError(f'禁止函数直接或间接递归: {function_id}')
        call_depth = int(caller.get('call_depth', 0)) + 1
        if call_depth > self.MAX_CALL_DEPTH:
            raise RuntimeError(f'函数调用深度超过上限 {self.MAX_CALL_DEPTH}')

        caller_variables = caller.get('variables') or {}
        child_variables = {
            key: value for key, value in caller_variables.items()
            if not str(key).startswith(('__param__:', '__local__:'))
        }
        declarations = {
            str(item.get('parameter_id') or ''): item
            for item in getattr(target, 'inputs', None) or []
            if isinstance(item, dict) and str(item.get('parameter_id') or '')
        }
        declaration_names = {
            str(item.get('name') or ''): item
            for item in declarations.values() if str(item.get('name') or '')
        }
        for declaration in declarations.values():
            default_value = declaration.get('default', declaration.get('default_value'))
            if default_value is not None:
                child_variables[f'__param__:{declaration["name"]}'] = self._coerce_call_value(
                    default_value, declaration.get('type')
                )
        bound_ids = set()
        for binding in call.get('input_bindings') or []:
            if not isinstance(binding, dict):
                continue
            parameter_id = str(binding.get('parameter_id') or binding.get('name') or '').strip()
            declaration = declarations.get(parameter_id) or declaration_names.get(parameter_id)
            if not declaration:
                continue
            raw_value = binding.get('value', binding.get('source'))
            value = self._resolve_call_value(caller_variables, raw_value)
            child_variables[f'__param__:{declaration["name"]}'] = self._coerce_call_value(value, declaration.get('type'))
            bound_ids.add(str(declaration.get('parameter_id') or ''))
        missing = [
            str(item.get('name') or item.get('parameter_id'))
            for item in declarations.values()
            if item.get('required') and f'__param__:{item.get("name")}' not in child_variables
        ]
        if missing:
            raise ValueError(f'缺少必填函数参数: {", ".join(missing)}')
        for local in getattr(target, 'local_variables', None) or []:
            if not isinstance(local, dict) or not str(local.get('name') or ''):
                continue
            child_variables[f'__local__:{local["name"]}'] = self._coerce_call_value(local.get('default', local.get('default_value')), local.get('type'))

        caller['paused_for_call'] = True
        self._call_stack.append({
            'task_id': function_id,
            'frame_kind': 'function',
            'start_node_id': getattr(target, 'entry_node_id', None),
            'entry_start_node_id': getattr(target, 'entry_node_id', None),
            'repeat_count': 1,
            'repeat_index': 0,
            'repeat_interval_ms': 0,
            'iteration_started': False,
            'variables': child_variables,
            'call_depth': call_depth,
            'return_to_frame': caller,
            'outcome_jumps': dict(outcome_jumps or {}),
            'output_bindings': list(call.get('output_bindings') or []),
        })
        self.log(f' [调用函数] {caller.get("task_id")} ➔ {function_id}（深度 {call_depth}）')

    def _resume_function_caller(self, child_frame: dict, result: dict):
        caller = child_frame.get('return_to_frame')
        if caller is None or caller not in self._call_stack:
            return
        caller_variables = caller.get('variables') or {}
        child_variables = child_frame.get('variables') or {}
        # Global/context values are shared semantically; parameter/local keys
        # never escape an invocation.
        for key, value in child_variables.items():
            if not str(key).startswith(('__param__:', '__local__:')):
                caller_variables[key] = value
        output_values = result.get('outputs') if isinstance(result.get('outputs'), dict) else {}
        for binding in child_frame.get('output_bindings') or []:
            if not isinstance(binding, dict):
                continue
            output_id = str(binding.get('output_id') or binding.get('source') or '').strip()
            target = str(binding.get('target') or '').strip()
            if output_id and target and output_id in output_values:
                self._write_scoped_value(caller_variables, target, output_values[output_id])
        outcome_id = str(result.get('outcome_id') or 'system_exception')
        jump = (child_frame.get('outcome_jumps') or {}).get(outcome_id)
        if not jump or not jump.target_node:
            caller['completion_pending'] = outcome_id != 'system_exception'
        else:
            caller['start_node_id'] = jump.target_node
            caller['iteration_started'] = True
        caller['variables'] = caller_variables
        caller['paused_for_call'] = False
        error = str(result.get('error') or '').strip()
        detail = f'，原因: {error}' if error else ''
        self.log(f' [函数返回] 结果={outcome_id}{detail}')

    @staticmethod
    def _scope_name(name: str) -> str:
        text = str(name or '').strip()
        for prefix in ('$var.', '$ctx.'):
            if text.startswith(prefix):
                return text[len(prefix):]
        if text.startswith('$local.'):
            return f'__local__:{text[len("$local."):]}'
        match = re.match(r'^\$(var|ctx|local)\{([^{}]+)\}$', text)
        if match:
            return f'__local__:{match.group(2).strip()}' if match.group(1) == 'local' else match.group(2).strip()
        return text

    def _read_scoped_value(self, variables: dict, source: str):
        return variables.get(self._scope_name(source))

    def _write_scoped_value(self, variables: dict, target: str, value):
        if str(target or '').strip().startswith(('$param.', '$param{')):
            raise ValueError('函数参数只读，不能作为输出写回目标')
        name = self._scope_name(target)
        if not name:
            raise ValueError('输出参数缺少写回目标')
        variables[name] = value

    def _resolve_call_value(self, variables: dict, raw_value):
        if not isinstance(raw_value, str):
            return raw_value
        value = raw_value.strip()
        if value.startswith(('$var.', '$ctx.', '$local.')) or re.match(r'^\$(var|ctx|local)\{', value):
            return self._read_scoped_value(variables, value)
        if value.startswith(('$param.', '$param{')):
            name = value.split('.', 1)[1] if value.startswith('$param.') else value[7:-1]
            return variables.get(f'__param__:{name}')
        if '$' in value:
            from core.expressions import evaluate_expression

            class _CallContext:
                pass
            ctx = _CallContext()
            ctx.variables = variables
            return evaluate_expression(value, ctx)
        return raw_value

    @staticmethod
    def _coerce_call_value(value, value_type):
        kind = str(value_type or 'any').lower()
        if value is None or kind in ('', 'any', 'string', 'str'):
            return '' if value is None and kind in ('string', 'str') else value
        if kind in ('integer', 'int'):
            return int(value)
        if kind in ('number', 'float'):
            return float(value)
        if kind in ('boolean', 'bool'):
            if isinstance(value, str):
                return value.strip().lower() in ('1', 'true', 'yes', 'on', '是')
            return bool(value)
        if kind in ('list', 'array'):
            if isinstance(value, list):
                return value
            if isinstance(value, tuple):
                return list(value)
            if isinstance(value, str):
                return [part.strip() for part in value.split(',') if part.strip()]
        return value

    # ========== P1 改造：图驱动路由处理器 ==========

    def _handle_jump(self, jump: Jump | None, node_id_to_index: dict, is_success: bool = True) -> bool:
        """
        P1 改造：图驱动路由处理器
        :return: True 表示需要返回到调用者（跨任务跳转完成或流程终止）
        """
        # 规则 1：无 Jump 或未指定 target_node -> 流程终点
        if not jump or not jump.target_node:
            self.log(' [Flow 终点] 当前输出端口未连线，分支流程自然结束')
            raise TaskIterationComplete('自然终点', success=is_success)

        self.log(f' [连线路由] → 目标节点: {jump.target_node}')

        # v3 不允许跨图连线；函数边界必须通过调用函数节点。
        if jump.target_task and jump.target_task != self.current_task_id:
            raise ValueError('检测到跨图连线；请改用调用函数节点')

                    # 规则 3：同流程精准节点跳转（O(1) 查找，替代 list.index()）
        target_idx = node_id_to_index.get(jump.target_node)
        if target_idx is not None:
            self.current_node_index = target_idx
        else:
            self.log(f' 找不到连线指向的目标节点 [{jump.target_node}]，流程终止', 'error')
            raise ValueError(f'目标节点不存在: {jump.target_node}')

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
            return PathResult(False, reason=f'流程 {task_id} 的邻接表不存在')

        graph = self._graph_cache[task_id]
        current_node_id = self.current_node.node_id if self.current_node else None
        if not current_node_id:
            return PathResult(False, reason='当前节点 ID 未知')

        return PathFinder.find_shortest_path(graph, current_node_id, target_node_id)

    def get_adjacency_graph(self, task_id: str = None) -> AdjacencyGraph | None:
        """获取指定流程的邻接表。"""
        task_id = task_id or self.current_task_id
        return self._graph_cache.get(task_id)

    def get_topology_graph(self) -> AdjacencyGraph | None:
        """获取拓扑地图邻接表"""
        return self._topology_graph

    def _topology_page_label(self, ref: str) -> str:
        """拓扑引用（page_id / node_id）→ 可读标签「组名/节点名」，找不到兜底原 id"""
        if not ref:
            return ''
        node_map, _ = self._build_topology_index()
        node = node_map.get(ref)
        topo = getattr(self.project, 'topology', None)
        if node is None and topo is not None:
            for task in topo.tasks:
                for nd in task.nodes:
                    if nd.node_id == ref:
                        node = nd
                        break
                if node is not None:
                    break
        # ⚡ 弹窗组节点不在主图索引中：从弹窗页列表反查（按 page_id 或 node_id）
        if node is None and self._popup_pages:
            for tid, pn in self._popup_pages:
                pid = TopologyMap.node_page_id(pn) or pn.node_id
                if pid == ref or pn.node_id == ref:
                    node = pn
                    break
        if node is None:
            return ref
        group_name = ''
        if topo is not None:
            for task in topo.tasks:
                if any(nd.node_id == node.node_id for nd in task.nodes):
                    group_name = task.task_name or task.task_id
                    break
        label = getattr(node, 'node_name', '') or TopologyMap.node_page_id(node) or ref
        return f'{group_name}/{label}' if group_name else label

    # ========== P3 新增：smart_jump 路径执行（当前页判定 + 沿途执行 + 每步位置监测） ==========

    def _build_topology_index(self) -> tuple[dict[str, Any], list[Any]]:
        """
        拓扑索引（懒构建）：拓扑键（页面键 = page_id、操作键 = node_id）→ Node 映射
        + page_state 节点列表（现场评估当前页用，不含弹窗组）
        """
        if getattr(self, '_topology_index', None) is not None:
            return self._topology_index
        node_map: dict[str, Any] = {}
        pages: list[Any] = []
        topo = getattr(self.project, 'topology', None)
        if topo is not None:
            seen_page_ids: dict[str, str] = {}
            for task in topo.tasks:
                for node in task.nodes:
                    if GraphBuilder.is_popup_node(node):
                        continue  # 弹窗页不参与普通导航页面评估
                    key = topo.node_page_id(node) or node.node_id
                    node_map[key] = node
                    if node.node_type == 'page_state':
                        page_id = topo.node_page_id(node)
                        if page_id:
                            # ⚡ page_id 唯一性校验：重复 id 会导致寻路与位置判定混淆
                            if page_id in seen_page_ids:
                                self.log(
                                    f' [页面状态] page_id 重复: [{page_id}] 同时属于 '
                                    f'[{seen_page_ids[page_id]}] 与 [{node.node_name}]，寻路可能混淆，请修改其中一个',
                                    'warning',
                                )
                            else:
                                seen_page_ids[page_id] = node.node_name or node.node_id
                        pages.append(node)
        self._topology_index = (node_map, pages)
        return self._topology_index

    def evaluate_current_page(self) -> str:
        """
        现场评估当前所在页面（⚡ 分层评估：已知当前页时优先评估邻接可达页面，
        1 跳 → 2 跳逐层扩大，均未命中才全图评估；当前页未知时直接全图）。
        首个命中（success）即当前页；全部未命中返回空串。
        匹配成功时 page_state 执行器会顺带写入 current_page_id。
        """
        _, pages = self._build_topology_index()
        if not pages:
            return ''
        from core.node_executors.base.page_state import PageStateNodeExecutor

        # ⚡ 共享截图：弹窗检查点已截过则复用，否则截一帧
        if self._step_screen is None:
            self._capture_workspace_step()

        evaluator = PageStateNodeExecutor()

        def _evaluate(node):
            try:
                result = evaluator.execute(node, self)
            except Exception as e:
                self.log(f'[智能跳转] 页面评估异常 [{node.node_name}]: {e}', 'warning')
                result = {'success': False}
            if result.get('success'):
                return {
                    'page_id': str((node.params or {}).get('page_id') or ''),
                    'node_name': node.node_name or node.node_id,
                    'feature_count': len((node.params or {}).get('features') or []),
                    'score': float(getattr(self, 'last_match_score', 0.0) or 0.0),
                }
            return None

        def _choose(matches: list[dict]) -> str:
            if not matches:
                return ''
            matches.sort(key=lambda item: (-item['feature_count'], -item['score'], item['node_name']))
            chosen = matches[0]
            if len(matches) > 1:
                labels = ', '.join(
                    f"{item['node_name']}(特征{item['feature_count']}, {item['score']:.2f})"
                    for item in matches[:6]
                )
                self.log(
                    f" [页面状态] 同一帧同时命中 {len(matches)} 个候选: {labels}；"
                    f"按特征数/置信度选择 [{chosen['node_name']}]",
                    'warning',
                )
            self.variables['current_page_id'] = chosen['page_id']
            return chosen['page_id']

        # 分层顺序：当前页邻接（1 跳）→ 2 跳 → 全图
        node_map, _ = self._build_topology_index()
        ordered: list[Any] = []
        seen: set[str] = set()
        current = self.variables.get('current_page_id', '')
        if current and self._topology_graph is not None:
            frontier = {current}
            for _ in range(2):  # 逐层扩展：1 跳 → 2 跳
                nxt: set[str] = set()
                for key in frontier:
                    for (tgt, _, _) in self._topology_graph.get_out_edges(key):
                        if tgt not in seen:
                            seen.add(tgt)
                            nxt.add(tgt)
                frontier = nxt
                if not frontier:
                    break
                for key in frontier:
                    node = node_map.get(key)
                    if node is not None and node.node_type == 'page_state' and node not in ordered:
                        ordered.append(node)
        ordered_matches = [hit for node in ordered if (hit := _evaluate(node))]
        if ordered_matches:
            return _choose(ordered_matches)
        # 全图兜底（含未知当前位置的首评）
        fallback_matches = []
        for page_node in pages:
            if page_node in ordered:
                continue
            hit = _evaluate(page_node)
            if hit:
                fallback_matches.append(hit)
        return _choose(fallback_matches)

    def _evaluate_expected_page(self, page_key: str) -> str:
        """Evaluate exactly one expected topology page on the current fresh frame.

        This is the fast path after a topology action.  It never replaces the
        existing stable-frame loader: a miss simply falls back to the normal
        load-wait and full navigation scan.
        """
        node_map, _ = self._build_topology_index()
        node = node_map.get(page_key)
        if node is None or node.node_type != 'page_state':
            return ''
        if self._step_screen is None and not self._capture_workspace_step():
            return ''
        from core.node_executors.base.page_state import PageStateNodeExecutor

        try:
            result = PageStateNodeExecutor().execute(node, self)
        except Exception as exc:
            self.log(f'[智能跳转] 目标页面即时评估异常 [{node.node_name}]: {exc}', 'warning')
            return ''
        if result.get('success'):
            return str((node.params or {}).get('page_id') or page_key)
        return ''

    def _resolve_current_page(self, timeout_ms: int = None) -> str:
        """读取或评估当前位置；指定超时时使用加载页等待策略。"""
        current = self.variables.get('current_page_id', '')
        if not current:
            if timeout_ms:
                current = self._resolve_current_page_with_load_wait(timeout_ms)
            else:
                current = self.evaluate_current_page()
            if current:
                self.variables['current_page_id'] = current
        return current

    def _frame_is_stable(self) -> bool:
        """帧稳定检测：当前 _step_screen 与上一帧比较（抽样像素差均值）。
        调用前需先 _capture_workspace_step() 刷新当前帧。"""
        frame = self._step_screen
        if frame is None:
            return False
        if self._prev_frame is None:
            self._prev_frame = frame
            return False
        import numpy as np

        try:
            a = np.array(self._prev_frame.convert('L'), dtype=np.int16)
            b = np.array(frame.convert('L'), dtype=np.int16)
            if a.shape != b.shape:
                self._prev_frame = frame
                return False
            # 等距抽样比较（步长 8），速度优先
            diff = float(np.abs(a[::8, ::8] - b[::8, ::8]).mean())
        except Exception:
            self._prev_frame = frame
            return False
        self._prev_frame = frame
        threshold = float(self.settings.get('frame_stable_threshold', 12))
        return diff < threshold

    def _resolve_current_page_with_load_wait(self, timeout_ms: int) -> str:
        """
        ⚡ 加载等待位置确认（方案 A+B）：页面跳转/加载期间不立即失败——
        画面变化大（加载动画）= 纯等待不识别；画面静止（连续 frame_stable_frames 帧）
        后识别一次；识别未命中继续轮询重试，直到命中或超时。
        超时窗口 = smart_jump 节点配置的 timeout（如新进游戏配 10s/20s）。
        :return: 命中的 page_id；超时返回空串
        """
        deadline = time.time() + max(100, int(timeout_ms or 0)) / 1000.0
        stable_frames = max(1, int(self.settings.get('frame_stable_frames', 2)))
        poll_ms = max(50, int(self.settings.get('page_load_poll_ms', 250)))
        anim_ms = max(50, int(self.settings.get('page_load_anim_wait_ms', 200)))
        waited = 0
        while time.time() < deadline:
            if self.is_stopped:
                return ''
            capture_result = self._capture_workspace_step()
            if capture_result is False:
                return ''
            if not self._frame_is_stable():
                # 加载动画中：纯等待，不识别（省 CPU）
                self._stable_frame_count = 0
                time.sleep(anim_ms / 1000.0)
                waited += anim_ms
                continue
            self._stable_frame_count += 1
            if self._stable_frame_count < stable_frames:
                time.sleep(poll_ms / 1000.0)
                waited += poll_ms
                continue
            # 画面已稳定：识别一次（复用本步共享截图）
            if not self._ensure_popups_clear(deadline):
                return ''
            current = self.evaluate_current_page()
            if current:
                self._stable_frame_count = 0
                self.log(
                    f' [智能跳转] 页面加载完成，已定位: [{self._topology_page_label(current)}]'
                    f'（加载等待 {waited}ms）'
                )
                return current
            # 一整轮普通页面未命中后，用新帧再次清场；用于捕获首轮清场后延迟出现的第二层弹窗。
            self._step_screen = None
            if not self._ensure_popups_clear(deadline):
                return ''
            if self._last_popup_result.get('handled_count'):
                self._stable_frame_count = 0
                self._prev_frame = None
                continue
            time.sleep(poll_ms / 1000.0)
            waited += poll_ms
        self.log(f'⏰ [智能跳转] 页面加载等待超时（{timeout_ms}ms），未能识别到任何已知页面', 'warning')
        return ''

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
        max_attempts = max(1, int(self.settings.get('smart_jump_attempts', 3)))
        retry_ms = max(100, int(self.settings.get('smart_jump_retry_ms', 500)))

        self.log(f'[智能跳转] 开始执行跳转 | 目标页面=[{self._topology_page_label(target)}] 超时={timeout}ms')

        for attempt in range(1, max_attempts + 1):
            if self.is_stopped:
                self.log('[智能跳转] 收到停止信号，终止跳转', 'warning')
                break
            if time.time() >= deadline:
                self.log('[智能跳转] 跳转超时（超过超时时间上限）', 'error')
                break

            # 首轮复用 smart_jump 执行器刚刚现场验证过的起点。两阶段同步相邻，
            # 中间没有任何动作或暂停点；重复扫描会白白消耗大部分跳转超时。
            current = str(path_info.get('verified_page_id') or '') if attempt == 1 else ''
            if current:
                self.log(f'[智能跳转] 复用刚刚验证的起点: [{self._topology_page_label(current)}]')
            else:
                # 重试时继续现场监测，保留用户手操/位置漂移后的动态重寻路能力。
                remain_ms = max(0, int((deadline - time.time()) * 1000))
                current = self._resolve_current_page_with_load_wait(remain_ms)
            if current:
                self.variables['current_page_id'] = current
            if current == target:
                self.log(f'[智能跳转] 已在目标页面 [{self._topology_page_label(target)}]')
                self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
                return True
            if not current:
                self.log('[智能跳转] 加载等待超时，无法确定当前位置，跳转失败', 'warning')
                break

            path_result = self.find_path_to_page(target)
            if not path_result.success or len(path_result.path) < 2:
                self.log(
                    f'[智能跳转] 第 {attempt} 次尝试：从 [{self._topology_page_label(current)}] 无路可达目标 [{self._topology_page_label(target)}]'
                    f'（{path_result.reason or "路径为空"}）',
                    'warning',
                )
                if attempt < max_attempts:
                    time.sleep(retry_ms / 1000.0)
                continue

            self.log(f'[智能跳转] 第 {attempt} 次尝试路径: {" → ".join(self._topology_page_label(x) for x in path_result.path)}')
            outcome = self._execute_topology_steps(path_result.path[1:], node_map, target, deadline)
            if outcome is True:
                self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
                self.log(f'[智能跳转] 跳转成功，已到达 [{self._topology_page_label(target)}]')
                return True
            if outcome == 'reroute':
                # 位置偏离路径预期（用户手操 / 识别漂移）→ 下一轮从新位置重新寻路
                self.log('[智能跳转] 位置偏离路径预期，从当前位置重新寻路', 'warning')
                continue
            # 路径执行失败（节点失败 / 路径耗尽未到达）→ 重试
            self.log('[智能跳转] 路径执行未到达目标，准备重试', 'warning')
            if attempt < max_attempts:
                time.sleep(0.5)

        self.variables.pop(SmartJumpNodeExecutor.PATH_VAR_KEY, None)
        self.log('[智能跳转] 跳转失败（超时 / 无路可达 / 重试用尽）', 'error')
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
                self.log('[智能跳转] 路径执行超时', 'warning')
                return False

            key = remaining.pop(0)
            node = node_map.get(key)
            if node is None:
                self.log(f'[智能跳转] 路径节点 [{key}] 无法解析', 'warning')
                return False

            # 智能跳转执行期间，路径上的识别/操作节点同样在动作前检查弹窗；
            # wait 等纯等待步骤不会触发弹窗或页面扫描。
            if self._node_requires_popup_check(node):
                if not self._ensure_popups_clear(deadline):
                    return False
                if self.is_stopped:
                    return False

            expected_page = ''
            if node.node_type != 'page_state':
                expected_page = next(
                    (
                        candidate for candidate in remaining
                        if candidate in node_map and node_map[candidate].node_type == 'page_state'
                    ),
                    '',
                )

            # Topology actions are transitions, not free-running click loops.
            # Only one input may be in flight; the destination page decides
            # whether the outer smart-jump attempt retries the edge.  Reusing
            # the same image asset on many game pages remains fully supported.
            execution_node = node
            execution_mode = str((node.params or {}).get('execution_mode') or '').lower()
            if (
                expected_page
                and node.node_type == 'image_recognition'
                and execution_mode in {'click_until_absent', 'click_until_stop'}
            ):
                execution_node = replace(
                    node,
                    params={**(node.params or {}), 'execution_mode': 'click_once'},
                )
                self.log(
                    f'[智能跳转] 导航单飞输入: [{node.node_name}] 本次仅点击一次，'
                    f'由目标页面 [{self._topology_page_label(expected_page)}] 确认后决定是否重试'
                )

            result = self._execute_node_safely(execution_node)
            ok = result.get('success', True)
            self.log(f'[智能跳转] 路径节点 [{node.node_name}] ({node.node_type}) 执行{"成功" if ok else "失败"}')
            if not ok:
                self.log(f'[智能跳转] 路径节点执行失败: {result.get("error", "")}', 'error')
                return False

            if node.node_type == 'page_state':
                current = str((node.params or {}).get('page_id') or key)
                self.variables['current_page_id'] = current
                if current == target:
                    self.log(f'[智能跳转] 位置确认：已到达目标页面 [{self._topology_page_label(target)}]')
                    return True
                continue

            # 点击完成后先抓一张新帧，只评估这条边的预期目标页面；若尚未
            # 出现，再回到原有稳定帧等待与全图扫描，保留慢页面可靠性。
            current = ''
            self._step_screen = None
            if expected_page and self._capture_workspace_step():
                current = self._evaluate_expected_page(expected_page)
                if current:
                    self.log(f'[智能跳转] 新帧即时命中目标页面: [{self._topology_page_label(current)}]')
            if not current:
                remain_ms = max(0, int((deadline - time.time()) * 1000))
                current = self._resolve_current_page_with_load_wait(remain_ms)
            if current:
                self.variables['current_page_id'] = current
            if current == target:
                self.log(f'[智能跳转] 位置确认：已到达目标页面 [{self._topology_page_label(target)}]')
                return True
            if current:
                if current in page_keys:
                    pos = page_keys.index(current)
                    # 当前页已经通过现场页面评估，不再重复执行同一个 page_state。
                    try:
                        skip = remaining.index(current)
                    except ValueError:
                        skip = -1
                    if skip >= 0:
                        self.log(f'[智能跳转] 位置推进至 [{self._topology_page_label(current)}]，跳过 {skip + 1} 个已确认步骤')
                        remaining = remaining[skip + 1:]
                    page_keys = page_keys[pos + 1:]
                    continue
                # 当前位置不在路径中（用户手操到别处 / 识别漂移）→ 重新寻路
                self.log(f'[智能跳转] 当前位置 [{self._topology_page_label(current)}] 不在路径中，需重新寻路')
                return 'reroute'

        # 路径执行完毕：加载等待确认一次位置（动画/延迟后仍识别不到则回退变量）
        remain_ms = max(0, int((deadline - time.time()) * 1000))
        current = self._resolve_current_page_with_load_wait(remain_ms)
        if not current:
            current = self.variables.get('current_page_id', '')
        if current == target:
            return True
        self.log(f'[智能跳转] 路径执行完毕但未确认到达目标页（当前 {current or "未知"}）', 'warning')
        return False

    # ========== 运行目标与上下文管理 ==========

    def get_window_rect(self):
        """返回实时工作区，避免窗口移动/缩放后继续使用陈旧坐标。"""
        from core.services.runtime_target import refresh_work_area

        return refresh_work_area(self)

    def is_window_mode(self):
        return self.window_hwnd is not None

    def _apply_context(self, context):
        def pick(*keys, default=None):
            for key in keys:
                if key in context and context[key] is not None:
                    return context[key]
            return default

        window_title = str(pick('window_title', 'windowTitle', default='') or '').strip()
        requested_work_mode = str(pick('work_mode', 'workMode', default='') or '').strip().lower()
        if requested_work_mode == 'desktop':
            window_title = ''
        is_android_target = requested_work_mode == 'android' or bool(
            pick('is_android', 'isAndroid', default=False)
        )
        if is_android_target:
            window_title = ''
        configured_emulator = bool(pick('is_emulator', 'isEmulator', default=False))
        is_emulator = configured_emulator or is_android_target
        # 模拟器输入和截图由 ADB 完成；在读取窗口几何前就标记目标类型，
        # 使最小化窗口也能使用项目配置的工作区尺寸初始化。
        self.is_emulator = is_emulator
        self.is_android_target = is_android_target
        offset_top = int(pick('offset_top', 'offsetTop', default=0) or 0)
        offset_bottom = int(pick('offset_bottom', 'offsetBottom', default=0) or 0)
        offset_left = int(pick('offset_left', 'offsetLeft', default=0) or 0)
        offset_right = int(pick('offset_right', 'offsetRight', default=0) or 0)
        target_w = int(pick('target_content_width', 'targetContentWidth', default=0) or 0)
        target_h = int(pick('target_content_height', 'targetContentHeight', default=0) or 0)

        # ⚡ $ctx{} 表达式可解析性：上下文字段写入 variables（裸键，与表达式 $ctx{xxx} 查询一致），
        # 全桌面模式（无窗口）也写入，保证节点参数里的 $ctx{...} 恒可解析
        ctx_vars = {
            'work_mode': 'android' if is_android_target else ('window' if window_title else 'desktop'),
            'title': window_title,
            'is_emulator': configured_emulator,
            'is_android': is_android_target,
            'content_offset': {
                'top': offset_top,
                'bottom': offset_bottom,
                'left': offset_left,
                'right': offset_right,
            },
            'target_content_size': [target_w, target_h],
        }
        for k, v in ctx_vars.items():
            self.variables[k] = v
            self._context_keys.add(k)
        # 表单开放的其它 ctx 自定义键也写入 variables（如 $ctx.max_retry 等）
        for k, v in context.items():
            if k not in ctx_vars and not k.startswith(('offset_', 'target_')):
                self.variables[k] = v
                self._context_keys.add(k)

        self.variables['window_content_offset'] = {
            'top': offset_top,
            'bottom': offset_bottom,
            'left': offset_left,
            'right': offset_right,
        }

        # A physical Android device (or an emulator intentionally used without
        # its Windows shell) is a first-class target.  Bind it before the
        # desktop/window branches: capture and input are both device-native and
        # no HWND exists or is required.
        if is_android_target:
            configured_device = str(pick('adb_device_id', 'adbDeviceId', default='') or '').strip()
            device_id = configured_device or self._auto_detect_device('')
            if not device_id:
                devices = self._get_adb_devices()
                detail = f'（当前设备: {", ".join(devices)}）' if devices else '（未发现在线设备）'
                raise RuntimeError(f'Android目标未绑定唯一 ADB serial{detail}，已阻止运行')
            if not self._check_device(device_id):
                raise RuntimeError(f'ADB 设备 [{device_id}] 不可用，已阻止运行')
            raw_w, raw_h = self._get_android_resolution(device_id)
            if not raw_w or not raw_h:
                raise RuntimeError(f'无法获取 Android 显示分辨率: {device_id}，已阻止运行')
            capture_w, capture_h = self._get_android_capture_resolution(device_id)
            if not capture_w or not capture_h:
                capture_w, capture_h = raw_w, raw_h
            if (
                target_w > 0
                and target_h > 0
                and (target_w, target_h) == (raw_w, raw_h)
                and (capture_w, capture_h) == (raw_h, raw_w)
            ):
                self.log(
                    f'[Android目标] 项目尺寸 {target_w}x{target_h} 是设备自然方向，'
                    f'已按当前画面纠正为 {capture_w}x{capture_h}',
                    'warning',
                )
                target_w, target_h = capture_w, capture_h
            work_w = target_w if target_w > 0 else capture_w
            work_h = target_h if target_h > 0 else capture_h
            self.window_hwnd = None
            self.device_id = device_id
            self.android_width = raw_w
            self.android_height = raw_h
            self.window_rect = (0, 0, int(work_w), int(work_h))
            self.variables['adb_device_id'] = device_id
            self.variables['android_width'] = raw_w
            self.variables['android_height'] = raw_h
            self.variables['target_content_size'] = [int(work_w), int(work_h)]
            self.variables['window_rect'] = self.window_rect
            self.log(
                f' [Android目标] 已绑定 {device_id} | 设备={raw_w}x{raw_h} | '
                f'当前画面={capture_w}x{capture_h} | 工作区={work_w}x{work_h}'
            )
            self._prewarm_android_runtime(device_id, (int(work_w), int(work_h)))
            return

        if not window_title:
            if is_emulator:
                raise RuntimeError('模拟器模式必须绑定目标窗口，已阻止运行')
            import pyautogui

            self.window_hwnd = None
            self.is_emulator = False
            self.device_id = None
            self.android_width = None
            self.android_height = None
            screen_w, screen_h = pyautogui.size()
            width = int(screen_w) - offset_left - offset_right
            height = int(screen_h) - offset_top - offset_bottom
            if width <= 0 or height <= 0:
                raise RuntimeError(
                    f'桌面裁剪后的工作区无效: ({offset_left}, {offset_top}, {width}, {height})'
                )
            self.window_rect = (offset_left, offset_top, width, height)
            self.variables['window_rect'] = self.window_rect
            self.log(
                'ℹ️ [目标绑定] 全桌面模式无定向后台输入后端；'
                '未开启物理输入回退时，点击节点会被明确阻止'
            )
            return

        self.log(f' [目标绑定] 寻找目标工作窗口: [{window_title}]')

        try:
            import win32con
            import win32gui
            import win32process
        except ImportError:
            raise RuntimeError('当前环境缺少 Windows 窗口绑定能力，已阻止运行')

        expected_hwnd = int(pick('window_hwnd', 'windowHwnd', default=0) or 0)
        expected_pid = int(pick('window_process_id', 'windowProcessId', default=0) or 0)
        expected_class = str(pick('window_class_name', 'windowClassName', default='') or '')

        def identity(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return {
                'hwnd': int(hwnd),
                'title': win32gui.GetWindowText(hwnd),
                'process_id': int(pid),
                'class_name': win32gui.GetClassName(hwnd),
            }

        hwnd = 0
        if expected_hwnd and win32gui.IsWindow(expected_hwnd):
            current = identity(expected_hwnd)
            if (
                current['title'] == window_title
                and (not expected_pid or current['process_id'] == expected_pid)
                and (not expected_class or current['class_name'] == expected_class)
            ):
                hwnd = expected_hwnd

        if not hwnd:
            candidates = []

            def enum_callback(candidate, _):
                try:
                    if not win32gui.IsWindowVisible(candidate):
                        return
                    candidate_identity = identity(candidate)
                    if candidate_identity['title'] != window_title:
                        return
                    if expected_class and candidate_identity['class_name'] != expected_class:
                        return
                    candidates.append(candidate_identity)
                except Exception:
                    return

            win32gui.EnumWindows(enum_callback, None)
            if expected_pid:
                pid_matches = [item for item in candidates if item['process_id'] == expected_pid]
                if len(pid_matches) == 1:
                    candidates = pid_matches
            if not candidates:
                raise RuntimeError(f'未找到已配置的目标窗口: [{window_title}]')
            if len(candidates) > 1:
                details = ', '.join(
                    f"hwnd={item['hwnd']}/pid={item['process_id']}" for item in candidates[:5]
                )
                raise RuntimeError(
                    f'存在多个同名目标窗口 [{window_title}]（{details}），'
                    '请在“工作面板设置”中重新选择具体实例'
                )
            hwnd = candidates[0]['hwnd']

        resolved = identity(hwnd)
        self.window_hwnd = hwnd
        self.variables['window_hwnd'] = resolved['hwnd']
        self.variables['window_process_id'] = resolved['process_id']
        self.variables['window_class_name'] = resolved['class_name']

        if target_w > 0 and target_h > 0 and not is_emulator:
            self.log(f'📏 [目标绑定] 执行窗口 Resize: {target_w}x{target_h}')
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

                flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                win32gui.SetWindowPos(hwnd, None, pos_x, pos_y, outer_w, outer_h, flags)
                self.log(f' [目标绑定] Resize 成功: {outer_w}x{outer_h}（未激活窗口）')
            except Exception as e:
                raise RuntimeError(f'目标窗口 Resize 失败，已阻止运行: {e}') from e
        elif target_w > 0 and target_h > 0 and is_emulator:
            self.log(f'📏 [目标绑定] ADB 工作区使用项目尺寸: {target_w}x{target_h}（不改变模拟器窗口）')

        from core.services.runtime_target import refresh_work_area

        self.window_rect = refresh_work_area(self)
        self.log(
            f' [目标绑定] 已绑定 hwnd={resolved["hwnd"]}, pid={resolved["process_id"]}, '
            f'工作区={self.window_rect}'
        )

        if not self.is_emulator:
            self.device_id = None
            self.android_width = None
            self.android_height = None
        if self.is_emulator:
            configured_device = str(pick('adb_device_id', 'adbDeviceId', default='') or '').strip()
            device_id = configured_device or self._auto_detect_device(window_title)
            if not device_id:
                devices = self._get_adb_devices()
                detail = f'（当前设备: {", ".join(devices)}）' if devices else '（未发现在线设备）'
                raise RuntimeError(
                    '模拟器未绑定唯一 ADB serial'
                    f'{detail}，已阻止运行；禁止回退 PC 或物理鼠标'
                )
            if not self._check_device(device_id):
                raise RuntimeError(f'ADB 设备 [{device_id}] 不可用，已阻止运行')
            self.device_id = device_id
            self.variables['adb_device_id'] = device_id
            android_w, android_h = self._get_android_resolution(device_id)
            if not android_w or not android_h:
                raise RuntimeError(f'无法获取 ADB 显示分辨率: {device_id}，已阻止运行')
            self.android_width = android_w
            self.android_height = android_h
            self.variables['android_width'] = android_w
            self.variables['android_height'] = android_h
            self.log(f' [目标绑定] 模拟器 ADB 绑定成功: {device_id} ({android_w}x{android_h})')
            self._prewarm_android_runtime(device_id, (int(self.window_rect[2]), int(self.window_rect[3])))

    def _prewarm_android_runtime(self, device_id, workspace_size):
        """Move Android stream startup outside each node's timeout budget."""

        try:
            from core.services.android_stream import get_android_video_session, validate_scrcpy_runtime

            available, detail = validate_scrcpy_runtime()
            if not available:
                self.log(f'[性能能力] Android高速会话不可用，将按节点策略处理: {detail}', 'warning')
                return False
            started = time.monotonic()
            session = get_android_video_session(self, workspace_size)
            session.start()
            elapsed_ms = (time.monotonic() - started) * 1000.0
            self.log(
                f'[性能能力] Android高速会话已预热: scrcpy持续画面 + 控制通道 ({elapsed_ms:.0f}ms)'
            )
            return True
        except Exception as exc:
            self.log(f'[性能能力] Android高速会话预热失败，将按节点策略处理: {exc}', 'warning')
            return False

    def _auto_detect_device(self, title):
        """仅接受可证明唯一的自动绑定；绝不取 devices 列表第一项。"""
        match = re.search(r'(\d{4,5})$', title)
        if match:
            port = match.group(1)
            candidates = [f'127.0.0.1:{port}', f'emulator-{port}']
            for candidate in candidates:
                if self._check_device(candidate):
                    return candidate
        devices = self._get_adb_devices()
        return devices[0] if len(devices) == 1 else None

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
                fields = line.split()
                if len(fields) >= 2 and fields[1] == 'device':
                    devices.append(fields[0])
            return devices
        except Exception:
            return []

    def _get_android_resolution(self, device_id):
        try:
            cmd = ['adb', '-s', device_id, 'shell', 'wm', 'size']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            output = result.stdout or ''
            match = re.search(r'Override size:\s*(\d+)x(\d+)', output, re.IGNORECASE)
            if not match:
                matches = re.findall(r'(\d+)x(\d+)', output)
                match = matches[-1] if matches else None
            if match:
                if isinstance(match, tuple):
                    return int(match[0]), int(match[1])
                return int(match.group(1)), int(match.group(2))
            return None, None
        except Exception:
            return None, None

    def _get_android_capture_resolution(self, device_id):
        """Read one device frame to obtain the current orientation and size."""
        try:
            import io

            from PIL import Image

            result = subprocess.run(
                ['adb', '-s', device_id, 'exec-out', 'screencap', '-p'],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0 or not result.stdout:
                return None, None
            image = Image.open(io.BytesIO(result.stdout))
            size = image.size
            image.close()
            return int(size[0]), int(size[1])
        except Exception:
            return None, None
