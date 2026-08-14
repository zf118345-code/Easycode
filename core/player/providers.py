# core/player/providers.py

import contextlib

import win32gui


class SystemDataProvider:
    """
    客户端动态数据源探针引擎
    为 Player 表单控件提供实时宿主机系统硬件/软件数据
    """

    @classmethod
    def get_window_list(cls) -> list[dict[str, str]]:
        """获取当前系统已打开且可见的窗口列表"""
        windows = []

        def enum_windows_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    windows.append({'label': title, 'value': title})
            return True

        with contextlib.suppress(Exception):
            win32gui.EnumWindows(enum_windows_callback, None)

        # 去重并按字母排序
        seen = set()
        unique_windows = []
        for w in windows:
            if w['value'] not in seen:
                seen.add(w['value'])
                unique_windows.append(w)

        return unique_windows

    @classmethod
    def get_monitors_list(cls) -> list[dict[str, str]]:
        """获取显示器分辨率列表（预设常规常见分辨率）"""
        return [
            {'label': '主显示器原始分辨率', 'value': 'native'},
            {'label': '1920 × 1080 (1080p 标准)', 'value': '1920x1080'},
            {'label': '2560 × 1440 (2K 极清)', 'value': '2560x1440'},
            {'label': '1366 × 768 (笔记本常用)', 'value': '1366x768'},
            {'label': '1280 × 720 (HD 720p)', 'value': '1280x720'},
        ]

    @classmethod
    def get_com_ports(cls) -> list[dict[str, str]]:
        """获取硬件串口/仿真端口列表"""
        ports = []
        try:
            import serial.tools.list_ports

            for p in serial.tools.list_ports.comports():
                ports.append({'label': f'{p.device} ({p.description})', 'value': p.device})
        except Exception:
            # 若未安装 pyserial，提供常见串口预设
            for i in range(1, 9):
                ports.append({'label': f'COM{i}', 'value': f'COM{i}'})

        return ports

    @classmethod
    def resolve_provider(cls, provider_key: str) -> list[dict[str, str]]:
        """统一 Handler 分发适配器"""
        if provider_key == 'sys.window_list':
            return cls.get_window_list()
        elif provider_key == 'sys.monitors':
            return cls.get_monitors_list()
        elif provider_key == 'sys.com_ports':
            return cls.get_com_ports()
        return []
