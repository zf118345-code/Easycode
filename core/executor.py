# core/executor.py
import time
import logging
import os
import shutil
from core.registry import NodeExecutorRegistry
from core.models import Task, Node, Jump

logger = logging.getLogger("GraphExecutor")

class GraphExecutor:
    def __init__(self, project, text_log_enabled=True, image_log_enabled=True):
        self.project = project
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

    def run(self, entry_task_id="main_task"):
        if self.text_log_enabled:
            logger.info(f"执行任务: {self.tasks[entry_task_id].task_name} (ID: {entry_task_id})")
        try:
            self._execute_task(entry_task_id)
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