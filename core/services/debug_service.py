# core/services/debug_service.py
# 断点执行 + 单步调试 + 变量运行时检查器
import json
import logging
import os
import threading
import time
from typing import Any

from fastapi import BackgroundTasks, HTTPException

from core.executor import GraphExecutor
from core.project_loader import load_project
from core.services.blueprint_service import BlueprintService

logger = logging.getLogger(__name__)


class DebugSession:
    """单次调试会话，管理断点、暂停、单步执行"""

    def __init__(self, session_id: str, executor: GraphExecutor, task_id: str, start_node_id: str = None):
        self.session_id = session_id
        self.executor = executor
        self.task_id = task_id
        self.start_node_id = start_node_id

        # 断点集合
        self.breakpoints: set[str] = set()

        # 调试控制事件
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始为非暂停状态
        self._step_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()  # 初始允许执行

        # 状态
        self._is_paused = False
        self._is_running = False
        self._current_node_id = None
        self._current_task_id = None
        self._pause_reason = None  # 'breakpoint' | 'step' | 'manual'

        # 暂停时的变量快照
        self._variable_snapshot = {}

        # 锁
        self._lock = threading.Lock()

    def add_breakpoint(self, node_id: str):
        """添加断点"""
        with self._lock:
            self.breakpoints.add(node_id)
            logger.info(f'调试 [{self.session_id}]: 添加断点 {node_id}')

    def remove_breakpoint(self, node_id: str):
        """移除断点"""
        with self._lock:
            self.breakpoints.discard(node_id)
            logger.info(f'调试 [{self.session_id}]: 移除断点 {node_id}')

    def clear_breakpoints(self):
        """清空所有断点"""
        with self._lock:
            self.breakpoints.clear()

    def get_breakpoints(self) -> list[str]:
        """获取所有断点"""
        with self._lock:
            return list(self.breakpoints)

    def should_pause(self, node_id: str) -> bool:
        """检查是否应该在当前节点暂停（由 executor 调用）"""
        with self._lock:
            if node_id in self.breakpoints:
                self._pause_reason = 'breakpoint'
                return True
            if self._step_event.is_set():
                self._step_event.clear()
                self._pause_reason = 'step'
                return True
        return False

    def pause(self):
        """手动暂停"""
        with self._lock:
            self._pause_reason = 'manual'
            self._is_paused = True

    def on_node_enter(self, node_id: str, task_id: str):
        """节点执行前回调（由 executor 调用）"""
        self._current_node_id = node_id
        self._current_task_id = task_id

        if self.should_pause(node_id):
            self._do_pause()

    def on_node_exit(self, node_id: str, success: bool, result: Any = None):
        """节点执行后回调"""
        pass

    def _do_pause(self):
        """执行暂停"""
        with self._lock:
            self._is_paused = True
            self._variable_snapshot = dict(self.executor.variables) if self.executor.variables else {}
            logger.info(f'调试 [{self.session_id}]: 暂停在节点 {self._current_node_id} (原因: {self._pause_reason})')

        # 等待恢复信号
        self._resume_event.clear()
        self._resume_event.wait()
        self._resume_event.set()

        with self._lock:
            self._is_paused = False
            self._pause_reason = None

    def resume(self):
        """恢复执行"""
        self._resume_event.set()
        logger.info(f'调试 [{self.session_id}]: 恢复执行')

    def step(self):
        """单步执行（执行一个节点后暂停）"""
        self._step_event.set()
        self.resume()

    def get_state(self) -> dict[str, Any]:
        """获取当前调试状态"""
        with self._lock:
            return {
                'session_id': self.session_id,
                'is_paused': self._is_paused,
                'is_running': self._is_running,
                'current_node_id': self._current_node_id,
                'current_task_id': self._current_task_id,
                'pause_reason': self._pause_reason,
                'breakpoints': list(self.breakpoints),
                'variables': dict(self._variable_snapshot) if self._is_paused else {},
                'executor_variables': dict(self.executor.variables) if self.executor.variables else {},
                'call_stack': getattr(self.executor, '_call_stack', []),
                'visited_count': dict(getattr(self.executor, '_visited_count', {})),
            }

    def stop(self):
        """停止调试会话"""
        self.executor.stop()
        self.resume()  # 释放暂停状态
        with self._lock:
            self._is_running = False


class DebugService:
    """调试服务：管理多个调试会话"""

    _sessions: dict[str, DebugSession] = {}
    _lock = threading.Lock()

    @staticmethod
    def start_debug_session(
        project_path: str,
        task_id: str,
        start_node_id: str = None,
        breakpoints: list[str] = None,
        blueprint_data: dict = None,
        background_tasks: BackgroundTasks = None,
    ) -> dict:
        """启动调试会话"""
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目不存在')

        # 保存蓝图
        if blueprint_data:
            BlueprintService.save_blueprint(project_path, blueprint_data)

        # 加载项目
        import pyautogui

        context_path = os.path.join(project_path, 'context.json')
        saved_context = {}
        if os.path.exists(context_path):
            with open(context_path, encoding='utf-8') as f:
                saved_context = json.load(f)

        project = load_project(project_path)
        session_id = f'debug_{task_id}_{int(time.time() * 1000)}'

        original_failsafe = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False

        executor = GraphExecutor(
            project,
            project_dir=project_path,
            text_log_enabled=True,
            image_log_enabled=True,
            initial_context=saved_context,
        )

        session = DebugSession(session_id, executor, task_id, start_node_id)

        # 设置初始断点
        if breakpoints:
            for bp in breakpoints:
                session.add_breakpoint(bp)

        with DebugService._lock:
            DebugService._sessions[session_id] = session

        def run_debug_background():
            try:
                session._is_running = True
                executor.run(task_id, start_node_id)
            except Exception as e:
                logger.error(f'调试会话异常: {e}', exc_info=True)
            finally:
                session._is_running = False
                pyautogui.FAILSAFE = original_failsafe
                with DebugService._lock:
                    DebugService._sessions.pop(session_id, None)

        if background_tasks:
            background_tasks.add_task(run_debug_background)
        else:
            thread = threading.Thread(target=run_debug_background, daemon=True)
            thread.start()

        return {'session_id': session_id, 'status': 'started', 'breakpoints': session.get_breakpoints()}

    @staticmethod
    def get_session_state(session_id: str) -> dict:
        """获取调试会话状态"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        return session.get_state()

    @staticmethod
    def add_breakpoint(session_id: str, node_id: str) -> dict:
        """添加断点"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.add_breakpoint(node_id)
        return {'status': 'success', 'breakpoints': session.get_breakpoints()}

    @staticmethod
    def remove_breakpoint(session_id: str, node_id: str) -> dict:
        """移除断点"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.remove_breakpoint(node_id)
        return {'status': 'success', 'breakpoints': session.get_breakpoints()}

    @staticmethod
    def resume_session(session_id: str) -> dict:
        """恢复执行"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.resume()
        return {'status': 'resumed'}

    @staticmethod
    def step_session(session_id: str) -> dict:
        """单步执行"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.step()
        return {'status': 'stepping'}

    @staticmethod
    def pause_session(session_id: str) -> dict:
        """暂停执行"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.pause()
        return {'status': 'paused'}

    @staticmethod
    def stop_session(session_id: str) -> dict:
        """停止调试会话"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        session.stop()
        return {'status': 'stopped'}

    @staticmethod
    def get_variables(session_id: str) -> dict:
        """获取当前变量"""
        with DebugService._lock:
            session = DebugService._sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='调试会话不存在')
        state = session.get_state()
        return {'variables': state.get('executor_variables', {})}

    @staticmethod
    def list_sessions() -> list:
        """列出所有活跃调试会话"""
        with DebugService._lock:
            return [
                {'session_id': sid, 'task_id': s.task_id, 'is_running': s._is_running}
                for sid, s in DebugService._sessions.items()
            ]
