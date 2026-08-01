# core/executor.py
import time
import logging
import os
import shutil
import win32gui
import win32con
import subprocess
import re
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

        # 窗口与模拟器全局上下文
        self.is_emulator = False
        self.device_id = None
        self.android_width = None
        self.android_height = None
        self.window_hwnd = None
        self.window_rect = None
        self.project_dir = project_dir

        # ⭐ 全局 Footer 预热：应用来自 Footer 的保存上下文（激活 + Resize + ADB设备挂载）
        if initial_context:
            self._apply_context(initial_context)

    def _clear_debug_dir(self):
        debug_dir = "debug_screenshots"
        if os.path.exists(debug_dir):
            shutil.rmtree(debug_dir)
        os.makedirs(debug_dir, exist_ok=True)

    def run(self, entry_task_id="main_task", start_node_id=None):
        logger.info(
            f"🚀 [Executor] 启动执行引擎 | 目标任务: {entry_task_id} | 起始节点: {start_node_id or '第一个节点'}")
        try:
            self._execute_task(entry_task_id, start_node_id)
        except StopIteration:
            logger.info("🏁 [Executor] 收到 StopIteration 指令，流程顺利结束")
        except Exception as e:
            logger.error(f"💥 [Executor] 发生未处理异常: {e}", exc_info=True)
            raise

    def _execute_task(self, task_id, start_node_id=None):
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        self.current_task = task
        self.current_task_id = task_id

        if start_node_id:
            idx = next((i for i, n in enumerate(task.nodes) if n.node_id == start_node_id), 0)
            self.current_node_index = idx
        else:
            self.current_node_index = 0

        node_count = len(task.nodes)
        logger.info(
            f"📋 [Task] 进入任务 [{task.task_name}] | 总节点数: {node_count} | 从索引 [{self.current_node_index}] 开始")

        while self.current_node_index < node_count and not self._stop:
            node = task.nodes[self.current_node_index]
            if node.enabled:
                result = self._execute_node(node)

                jump = None
                if "jump" in result:
                    jump = self._dict_to_jump(result["jump"])
                elif result.get("success") and node.on_success:
                    jump = node.on_success
                elif not result.get("success") and node.on_failure:
                    jump = node.on_failure

                if jump:
                    self._handle_jump(jump)
                else:
                    self.current_node_index += 1
            else:
                logger.info(f"⏸️ [Node] 节点 [{node.node_name}] (ID: {node.node_id}) 已禁用，自动跳过")
                self.current_node_index += 1

    def _execute_node(self, node):
        executor_class = NodeExecutorRegistry.get(node.node_type)
        if not executor_class:
            logger.warning(f"❌ [Node] 未找到节点类型对应的执行器: {node.node_type}")
            return {"success": False, "error": "executor not found"}

        executor = executor_class()

        if node.delay_before > 0:
            logger.info(f"⏱️ [Node] 前置延迟: {node.delay_before} ms")
            time.sleep(node.delay_before / 1000.0)

        loop_count = node.loop_count if node.loop_count != -1 else float('inf')
        result = None

        self.current_node = node
        self.current_node_index = self.current_node_index
        self.current_task_name = self.current_task.task_name if self.current_task else "unknown"

        logger.info(f"▶️ [Node 执行] 第 {self.current_node_index + 1} 个 | [{node.node_name}] ({node.node_type})")
        start_time = time.time()

        for i in range(int(loop_count)):
            result = executor.execute(node, self)
            if result.get("success") and node.loop_count != -1:
                break
            if not result.get("success"):
                break

        elapsed = (time.time() - start_time) * 1000
        status_str = "✅ 成功" if result.get("success") else "❌ 失败"
        logger.info(f"⏹️ [Node 完成] {status_str} | 耗时: {elapsed:.2f}ms | 结果: {result}")

        return result or {"success": False}

    def _handle_jump(self, jump):
        logger.info(f"🔀 [Jump 路由] 类型: {jump.type} | 目标任务: {jump.target} | 目标节点: {jump.target_node}")

        if jump.type == "next" or not jump.type:
            self.current_node_index += 1

        elif jump.type == "node":
            target_node = next((n for n in self.current_task.nodes if n.node_id == jump.target_node), None)
            if target_node:
                self.current_node_index = self.current_task.nodes.index(target_node)
            else:
                logger.error(f"❌ 未在当前任务中找到目标节点: {jump.target_node}，默认推进到下一节点")
                self.current_node_index += 1

        elif jump.type == "task":
            self._execute_task(jump.target, jump.target_node)
            if not jump.return_on_complete:
                self._stop = True

        elif jump.type == "end":
            self._stop = True
            raise StopIteration()

        else:
            self.current_node_index += 1

    def _dict_to_jump(self, d):
        if isinstance(d, Jump):
            return d
        return Jump(
            type=d.get("type", "next"),
            target=d.get("target") or d.get("target_task"),
            target_node=d.get("target_node"),
            return_on_complete=d.get("return_on_complete", False)
        )

    def get_window_rect(self):
        if self.window_rect is not None:
            return self.window_rect
        import pyautogui
        w, h = pyautogui.size()
        return (0, 0, w, h)

    def is_window_mode(self):
        return self.window_rect is not None

    def log(self, msg, level="info"):
        if level == "info":
            logger.info(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg)

    # ⭐ 全局 Footer 预热逻辑（补齐 ADB 设备与物理分辨率全自动检测）
    def _apply_context(self, context):
        window_title = context.get("window_title") or context.get("windowTitle", "")
        if not window_title:
            logger.info("ℹ️ [Footer 预热] 当前为全桌面模式，无需预热窗口")
            return

        logger.info(f"🔍 [Footer 预热] 发现全局工作窗口设置，正在寻找窗口: [{window_title}]")
        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            logger.warning(f"⚠️ [Footer 预热] 未能找到指定窗口: [{window_title}]")
            return

        # 1. 安全置顶并激活窗口 (引入 win32con.keybd_event 绕过 Windows 前台限制)
        try:
            import win32com.client
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # 模拟 ALT 按键绕过 Windows SetForegroundWindow 拦截
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            logger.info(f"✅ [Footer 预热] 窗口已自动激活置顶: {window_title}")
        except Exception:
            # 即使捕捉到拦截异常也静默忽略，不影响后文的挂载与截图
            pass

        # 2. 获取裁剪偏移
        offset_top = context.get("offset_top") or context.get("offsetTop", 0)
        offset_bottom = context.get("offset_bottom") or context.get("offsetBottom", 0)
        offset_left = context.get("offset_left") or context.get("offsetLeft", 0)
        offset_right = context.get("offset_right") or context.get("offsetRight", 0)

        # 3. 如果 Footer 设定了目标尺寸，执行强制 Resize
        target_w = context.get("target_content_width") or context.get("targetContentWidth", 0)
        target_h = context.get("target_content_height") or context.get("targetContentHeight", 0)

        if target_w > 0 and target_h > 0:
            logger.info(f"📏 [Footer 预热] 监测到目标尺寸 {target_w}x{target_h}，正在执行自动 Resize...")
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
                logger.info(f"✅ [Footer 预热] 窗口尺寸重置成功: 外框 {outer_w}x{outer_h}")
            except Exception as e:
                logger.warning(f"⚠️ [Footer 预热] Resize 窗口失败: {e}")

        # 4. 计算客户区
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
            self.variables["window_content_offset"] = {
                "top": offset_top, "bottom": offset_bottom,
                "left": offset_left, "right": offset_right
            }
            self.variables["window_rect"] = self.window_rect
            logger.info(f"🎯 [Footer 预热] 最终挂载全局工作区域: {self.window_rect}")

        # 5. ⭐ 核心修复：全自动挂载模拟器 ADB 设备与物理分辨率
        self.is_emulator = context.get("is_emulator") or context.get("isEmulator", False)
        if self.is_emulator:
            device_id = self._auto_detect_device(window_title)
            if device_id:
                self.device_id = device_id
                android_w, android_h = self._get_android_resolution(device_id)
                if android_w and android_h:
                    self.android_width = android_w
                    self.android_height = android_h
                    self.variables["android_width"] = android_w
                    self.variables["android_height"] = android_h
                    logger.info(
                        f"🤖 [Footer 预热] 模拟器绑定成功! 设备: {device_id} | Android 物理分辨率: {android_w}x{android_h}")
                else:
                    logger.warning(f"⚠️ [Footer 预热] 设备 {device_id} 无法获取 Android 分辨率")
            else:
                logger.warning("⚠️ [Footer 预热] 未找到匹配的 ADB 设备，模拟器模式将自动回退为桌面鼠标点击")
                self.is_emulator = False

    # ---------- 辅助检测工具函数 ----------
    def _auto_detect_device(self, title):
        match = re.search(r'(\d{4,5})$', title)
        if match:
            port = match.group(1)
            candidates = [f"127.0.0.1:{port}", f"emulator-{port}"]
            for candidate in candidates:
                if self._check_device(candidate):
                    return candidate
        devices = self._get_adb_devices()
        return devices[0] if devices else None

    def _check_device(self, device_id):
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "echo", "test"],
                capture_output=True, text=True, timeout=2
            )
            return result.returncode == 0 and "test" in result.stdout
        except:
            return False

    def _get_adb_devices(self):
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            for line in lines:
                if "device" in line and "offline" not in line:
                    devices.append(line.split()[0])
            return devices
        except:
            return []

    def _get_android_resolution(self, device_id):
        try:
            cmd = ["adb", "-s", device_id, "shell", "wm", "size"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None, None
        except:
            return None, None