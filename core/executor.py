# core/executor.py
import time
import logging
import os
import shutil
from core.registry import NodeExecutorRegistry
from core.models import Task, Node, Jump

logger = logging.getLogger(__name__)

class GraphExecutor:
    def __init__(self, project, project_dir=None, text_log_enabled=True, image_log_enabled=True, initial_context=None):
        self.project = project
        self.project_dir = project_dir  # 新增
        self.tasks = project.tasks
        self.variables = project.variables.copy()
        self.current_task = None
        self.current_task_id = None
        self.current_node_index = 0
        self._stop = False
        self.window_hwnd = None
        self.window_rect = None
        self.text_log_enabled = text_log_enabled
        self.image_log_enabled = image_log_enabled
        self._clear_debug_dir()
        self.is_emulator = False
        self.device_id = None
        self.android_width = None
        self.android_height = None

        # 应用保存的上下文
        if initial_context:
            self._apply_context(initial_context)

    def _apply_context(self, context):
        """应用保存的上下文到执行器"""
        # 支持两种命名方式
        window_title = context.get("window_title") or context.get("windowTitle", "")
        if not window_title:
            print("上下文中没有窗口标题，跳过窗口设置")
            return

        import win32gui
        import win32con
        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            print(f"未找到窗口: {window_title}")
            return

        # 激活窗口
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            print(f"窗口已激活: {window_title}")
        except Exception as e:
            print(f"激活窗口失败: {e}")

        # 获取客户区
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

        # 应用裁剪（支持两种命名）
        offset_top = context.get("offset_top") or context.get("offsetTop", 0)
        offset_bottom = context.get("offset_bottom") or context.get("offsetBottom", 0)
        offset_left = context.get("offset_left") or context.get("offsetLeft", 0)
        offset_right = context.get("offset_right") or context.get("offsetRight", 0)

        new_left = left + offset_left
        new_top = top + offset_top
        new_width = (right - left) - offset_left - offset_right
        new_height = (bottom - top) - offset_top - offset_bottom

        if new_width > 0 and new_height > 0:
            self.window_rect = (new_left, new_top, new_width, new_height)
            self.window_hwnd = hwnd
            print(f"应用上下文窗口: {window_title}, 区域: {self.window_rect}")
        else:
            print(f"裁剪后区域无效: {new_width}x{new_height}")

        # 模拟器模式（支持两种命名）
        self.is_emulator = context.get("is_emulator") or context.get("isEmulator", False)
        if self.is_emulator:
            self.device_id = context.get("device_id") or context.get("deviceId", "")
            self.android_width = context.get("android_width") or context.get("androidWidth", 0)
            self.android_height = context.get("android_height") or context.get("androidHeight", 0)
            print(f"应用上下文: 模拟器模式, 设备: {self.device_id}, 分辨率: {self.android_width}x{self.android_height}")

    def _clear_debug_dir(self):
        debug_dir = "debug_screenshots"
        if os.path.exists(debug_dir):
            shutil.rmtree(debug_dir)
        os.makedirs(debug_dir, exist_ok=True)
        if self.text_log_enabled:
            logger.info(f"已清空调试截图目录: {debug_dir}")

    def set_text_log_enabled(self, enabled):
        self.text_log_enabled = enabled

    def set_image_log_enabled(self, enabled):
        self.image_log_enabled = enabled

    def run(self, entry_task_id="main_task", start_node_id=None):
        if self.text_log_enabled:
            logger.info(f"执行任务: {self.tasks[entry_task_id].task_name} (ID: {entry_task_id})")
        try:
            self._execute_task(entry_task_id, start_node_id)
        except StopIteration:
            if self.text_log_enabled:
                logger.info("流程正常结束")
        except Exception as e:
            logger.error(f"执行异常: {e}")
            raise

    def _execute_task(self, task_id, start_node_id=None):
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        self.current_task = task
        self.current_task_id = task_id
        if start_node_id:
            idx = None
            for i, n in enumerate(task.nodes):
                if n.node_id == start_node_id:
                    idx = i
                    break
            self.current_node_index = idx if idx is not None else 0
        else:
            self.current_node_index = 0
        node_count = len(task.nodes)
        while self.current_node_index < node_count and not self._stop:
            node = task.nodes[self.current_node_index]
            if node.enabled:
                result = self._execute_node(node)
                jump = None
                if result.get("success") and node.on_success:
                    jump = node.on_success
                elif not result.get("success") and node.on_failure:
                    jump = node.on_failure
                if "jump" in result:
                    jump = self._dict_to_jump(result["jump"])
                if jump:
                    self._handle_jump(jump)
                    continue
                self.current_node_index += 1
            else:
                self.current_node_index += 1

    def _execute_node(self, node):
        if not self._check_execution_condition(node):
            return {"success": True, "skip": True}
        executor_class = NodeExecutorRegistry.get(node.node_type)
        if not executor_class:
            if self.text_log_enabled:
                logger.warning(f"未找到节点执行器: {node.node_type}")
            return {"success": False, "error": "executor not found"}
        executor = executor_class()
        if node.delay_before > 0:
            time.sleep(node.delay_before / 1000.0)
        loop_count = node.loop_count if node.loop_count != -1 else float('inf')
        result = None
        context = self
        context.current_node = node
        context.current_node_index = self.current_node_index
        context.current_task_name = self.current_task.task_name if self.current_task else "unknown"
        context.current_task_id = self.current_task_id

        for i in range(int(loop_count)):
            result = executor.execute(node, context)
            if result.get("success") and node.loop_count != -1:
                break
            if not result.get("success"):
                break
        return result or {"success": False}

    def _check_execution_condition(self, node):
        cond = node.execution_condition
        if cond is None or cond.type == "always":
            return True
        return True

    def _handle_jump(self, jump):
        if self.text_log_enabled:
            logger.info(f"执行跳转: type={jump.type}, target={jump.target}, target_node={jump.target_node}")
        if jump.type == "next":
            self.current_node_index += 1
        elif jump.type == "node":
            target_node = next((n for n in self.current_task.nodes if n.node_id == jump.target), None)
            if target_node:
                self.current_node_index = self.current_task.nodes.index(target_node)
            else:
                if self.text_log_enabled:
                    logger.error(f"未找到目标节点: {jump.target}")
        elif jump.type == "task":
            self._execute_task(jump.target, jump.target_node)
            if not jump.return_on_complete:
                self._stop = True
        elif jump.type == "end":
            self._stop = True
            raise StopIteration()
        else:
            if self.text_log_enabled:
                logger.error(f"未知跳转类型: {jump.type}")

    def _dict_to_jump(self, d):
        return Jump(type=d.get("type", "next"),
                    target=d.get("target"),
                    target_node=d.get("target_node"),
                    return_on_complete=d.get("return_on_complete", False))

    def get_window_rect(self):
        if self.window_rect is not None:
            return self.window_rect
        import pyautogui
        w, h = pyautogui.size()
        return (0, 0, w, h)

    def is_window_mode(self):
        return self.window_rect is not None

    def log(self, msg, level="info"):
        if not self.text_log_enabled:
            return
        if level == "info":
            logger.info(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg)