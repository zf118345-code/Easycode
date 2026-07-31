# core/executor.py
import time
import logging
import os
import shutil
import win32gui
import win32con
from core.registry import NodeExecutorRegistry
from core.models import Task, Node, Jump

logger = logging.getLogger(__name__)

class GraphExecutor:
    def __init__(self, project, project_dir=None, text_log_enabled=True, image_log_enabled=True, initial_context=None):
        self.project = project
        self.tasks = project.tasks
        self.variables = project.variables.copy()
        self.current_task = None
        self.current_task_id = None
        self.current_node_index = 0
        self._stop = False
        self.text_log_enabled = text_log_enabled
        self.image_log_enabled = image_log_enabled
        self._clear_debug_dir()

        # 窗口上下文
        self.is_emulator = False
        self.device_id = None       # 由 set_window 节点动态设置
        self.android_width = None   # 由 set_window 节点动态设置
        self.android_height = None  # 由 set_window 节点动态设置
        self.window_hwnd = None
        self.window_rect = None
        self.project_dir = project_dir

        # 应用保存的上下文
        if initial_context:
            self._apply_context(initial_context)

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

    # ====== 应用上下文（核心方法） ======
    def _apply_context(self, context):
        """应用保存的上下文到执行器"""
        import json
        print("\n" + "=" * 60)
        print("📥 [应用上下文] 执行器收到的上下文数据:")
        print(json.dumps(context, indent=2, ensure_ascii=False))
        print("=" * 60 + "\n")

        # 支持两种命名方式：下划线 和 驼峰
        window_title = context.get("window_title") or context.get("windowTitle", "")
        if not window_title:
            print("⚠️ [应用上下文] 上下文中没有窗口标题，跳过窗口设置")
            return

        print(f"🔍 [应用上下文] 尝试查找窗口: {window_title}")
        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            print(f"❌ [应用上下文] 未找到窗口: {window_title}")
            return

        # 激活窗口
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            print(f"✅ [应用上下文] 窗口已激活: {window_title}")
        except Exception as e:
            print(f"⚠️ [应用上下文] 激活窗口失败: {e}")

        # 获取客户区
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

        # 应用裁剪
        offset_top = context.get("offset_top") or context.get("offsetTop", 0)
        offset_bottom = context.get("offset_bottom") or context.get("offsetBottom", 0)
        offset_left = context.get("offset_left") or context.get("offsetLeft", 0)
        offset_right = context.get("offset_right") or context.get("offsetRight", 0)

        new_left = left + offset_left
        new_top = top + offset_top
        new_width = (right - left) - offset_left - offset_right
        new_height = (bottom - top) - offset_top - offset_bottom

        print(f"📐 [应用上下文] 窗口原始客户区: 左上({left},{top}) 宽{right - left} 高{bottom - top}")
        print(
            f"📐 [应用上下文] 裁剪偏移: top={offset_top}, bottom={offset_bottom}, left={offset_left}, right={offset_right}")
        print(f"📐 [应用上下文] 裁剪后区域: 左上({new_left},{new_top}) 宽{new_width} 高{new_height}")

        if new_width > 0 and new_height > 0:
            self.window_rect = (new_left, new_top, new_width, new_height)
            self.window_hwnd = hwnd
            print(f"✅ [应用上下文] 窗口区域已设置: {self.window_rect}")
            # ====== 关键修复：存储 content_offset 到 variables ======
            self.variables["window_content_offset"] = {
                "top": offset_top,
                "bottom": offset_bottom,
                "left": offset_left,
                "right": offset_right
            }
            print(f"📌 [应用上下文] 已存储 content_offset: {self.variables['window_content_offset']}")
        else:
            print(f"❌ [应用上下文] 裁剪后区域无效: {new_width}x{new_height}")

        # 模拟器模式
        self.is_emulator = context.get("is_emulator") or context.get("isEmulator", False)
        if self.is_emulator:
            print(f"📱 [应用上下文] 模拟器模式: 已启用（设备信息由 set_window 节点自动检测）")

        # ====== 新增：如果上下文中包含目标内容尺寸，则 resize 窗口 ======
        target_w = context.get("target_content_width") or context.get("targetContentWidth")
        target_h = context.get("target_content_height") or context.get("targetContentHeight")
        if target_w and target_h and hwnd:
            print(f"📏 [应用上下文] 检测到目标内容尺寸: {target_w}x{target_h}，开始调整窗口...")
            try:
                # 获取当前窗口位置
                window_rect = win32gui.GetWindowRect(hwnd)
                pos_x, pos_y = window_rect[0], window_rect[1]

                # 获取边框尺寸
                cur_client_rect = win32gui.GetClientRect(hwnd)
                cur_window_rect = win32gui.GetWindowRect(hwnd)
                border_w = (cur_window_rect[2] - cur_window_rect[0]) - cur_client_rect[2]
                border_h = (cur_window_rect[3] - cur_window_rect[1]) - cur_client_rect[3]

                # 目标客户区尺寸 = 内容尺寸 + 偏移
                client_w = target_w + offset_left + offset_right
                client_h = target_h + offset_top + offset_bottom

                outer_w = client_w + border_w
                outer_h = client_h + border_h

                print(f"📏 [应用上下文] 边框尺寸: 宽{border_w} 高{border_h}")
                print(f"📏 [应用上下文] 目标客户区: {client_w}x{client_h}")
                print(f"📏 [应用上下文] 目标外边框: {outer_w}x{outer_h}")

                win32gui.SetWindowPos(hwnd, None, pos_x, pos_y, outer_w, outer_h,
                                      win32con.SWP_NOZORDER)
                print(
                    f"✅ [应用上下文] 窗口已调整: 外边框 {outer_w}x{outer_h}，客户区 {client_w}x{client_h}，内容区 {target_w}x{target_h}")

                # 更新 window_rect
                new_left, new_top = win32gui.ClientToScreen(hwnd, (0, 0))
                new_right, new_bottom = win32gui.ClientToScreen(hwnd, (client_w, client_h))
                self.window_rect = (new_left + offset_left, new_top + offset_top,
                                    client_w - offset_left - offset_right,
                                    client_h - offset_top - offset_bottom)
                print(f"✅ [应用上下文] 更新后的窗口区域: {self.window_rect}")
            except Exception as e:
                print(f"❌ [应用上下文] resize 失败: {e}")
        else:
            print("ℹ️ [应用上下文] 上下文中未设置目标内容尺寸，跳过 resize")

        print("=" * 60 + "\n")