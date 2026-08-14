# core/conditions/handlers/window_state.py
import contextlib
from typing import Any

import win32gui

from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register('window_state')
class WindowStateEvaluator(BaseConditionEvaluator):
    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        raw_title = str(params.get('window_title', '')).strip()
        state = str(params.get('state_check') or params.get('state', 'exists'))

        if not raw_title:
            return False

        # ⚡ 解析命名空间变量
        window_title = resolve_template_string(raw_title, context)

        found_hwnd = 0

        def enum_windows_callback(hwnd, extra):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if window_title.lower() in title.lower():
                    found_hwnd = hwnd
                    return False
            return True

        with contextlib.suppress(Exception):
            win32gui.EnumWindows(enum_windows_callback, None)

        if state == 'exists':
            return found_hwnd != 0
        elif state in ('closed', 'not_exists'):
            return found_hwnd == 0
        elif state == 'active':
            if found_hwnd == 0:
                return False
            foreground_hwnd = win32gui.GetForegroundWindow()
            return found_hwnd == foreground_hwnd

        return False
