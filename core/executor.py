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

    def __init__(self, project, project_dir=None, text_log_enabled=True, image_log_enabled=True, initial_context=None):
        self.project = project
        self.tasks = project.tasks
        self.variables = project.variables.copy()
        self.current_task = None
        self.current_task_id = None
        self.current_node_index = 0
        self.current_node = None
        self.current_task_name = 'unknown'

        # P0 修复：停止标志 + 线程锁
        self._stop = False
        self._stop_lock = threading.Lock()

        self.text_log_enabled = text_log_enabled
        self.image_log_enabled = image_log_enabled

        # P0 修复：线程安全日志列表
        self._logs_lock = threading.Lock()
        self.logs: list[dict] = []

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
            if topology and topology.nodes:
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

        # P0 修复：线程安全写入
        with self._logs_lock:
            self.logs.append(log_item)

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

            # 执行节点
            result = self._execute_node_safely(node)

            # 路由决策
            jump = None
            is_success = result.get('success', True)

            # 优先级：执行器返回的 jump > node.on_failure > node.on_success
            if 'jump' in result and result['jump']:
                jump = Jump.from_dict(result['jump'])
            elif not is_success and node.on_failure:
                jump = node.on_failure
            elif is_success and node.on_success:
                jump = node.on_success

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
            return {'success': False, 'error': str(err), 'jump': node.on_failure.to_dict() if node.on_failure else None}

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
