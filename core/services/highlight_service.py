# core/services/highlight_service.py
# ⚡ 全局控件高亮服务：全屏分层置顶窗口，GDI 绘制纯边框（无标签、无横幅——所有附加悬浮信息已移除）
# 特性：
#   - 覆盖整个虚拟屏幕（多显示器），物理像素坐标 → 与 UIA 返回零偏移
#   - WS_EX_TRANSPARENT + WS_EX_NOACTIVATE：鼠标点击/键盘穿透，不影响任何操作
#   - LWA_COLORKEY 色键透明：仅边框可见，其余区域完全透明
#   - frames 无变化时跳过重绘（省资源）
import logging
import threading

import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

_COLORKEY = win32api.RGB(1, 1, 1)            # 透明色键（近黑，避免与高亮色冲突）
_ACTIVE_COLOR = win32api.RGB(0, 229, 255)    # 选中控件：实线 2px 青色

WINDOW_TITLE = 'EasycodeHighlight'           # 供捕获服务识别自家窗口（防御过滤）


class HighlightService:
    """全局控件高亮（单例由路由层持有）
    ⚡ 渲染线程模型：所有窗口操作（创建/绘制/销毁）都收敛到专用渲染线程串行执行。
    曾经的实现由任意工作线程直接操作窗口——pywin32 的 MFC 窗口对象跨线程使用会触发
    原生崩溃（Access Violation，进程无 Python 异常直接退出），这是后端"莫名断开"的根因。
    render 保持同步语义（返回时绘制已完成）。"""

    def __init__(self):
        self._cond = threading.Condition()
        self._render_thread = None
        self._render_pending = False
        self._quit = False
        self._hwnd = None
        self._last_key = None
        self._current_frames = []

    # ------------------------------------------------------------------ 渲染线程

    def _ensure_render_thread(self):
        if self._render_thread is None or not self._render_thread.is_alive():
            self._render_thread = threading.Thread(
                target=self._render_loop, daemon=True, name='highlight-render')
            self._render_thread.start()

    def _render_loop(self):
        """专用渲染线程：串行执行所有窗口操作（创建/绘制/销毁），杜绝跨线程 GDI"""
        with self._cond:
            while not self._quit:
                while not self._render_pending and not self._quit:
                    self._cond.wait(1.0)
                if self._quit:
                    break
                self._render_pending = False
                try:
                    self._do_render(self._current_frames)
                except Exception as e:
                    logger.error('高亮渲染异常: %s', e)
                finally:
                    self._cond.notify_all()  # 唤醒等待本次渲染完成的调用方

    def _schedule_render(self):
        """（持锁调用）请求渲染并等待渲染线程完成（同步语义）"""
        self._render_pending = True
        self._ensure_render_thread()
        self._cond.notify_all()
        while self._render_pending:
            self._cond.wait(1.0)

    def _do_render(self, frames):
        """（渲染线程内）实际绘制：空帧销毁窗口，否则创建/重绘窗口（只画边框，无任何文字）"""
        if not frames:
            self._destroy_window()
            return
        vx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        vy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        vw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        vh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        self._ensure_window(vx, vy, vw, vh)
        if not self._hwnd:
            return
        hwnd = self._hwnd
        hdc = win32gui.GetDC(hwnd)
        try:
            # 清屏为透明色键
            brush = win32gui.CreateSolidBrush(_COLORKEY)
            win32gui.FillRect(hdc, (0, 0, vw, vh), brush)
            win32gui.DeleteObject(brush)

            null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
            for f in frames:
                rect = f['rect']
                r = (rect[0] - vx, rect[1] - vy, rect[2] - vx, rect[3] - vy)
                pen = win32gui.CreatePen(win32con.PS_SOLID, 2, _ACTIVE_COLOR)
                old_pen = win32gui.SelectObject(hdc, pen)
                old_brush = win32gui.SelectObject(hdc, null_brush)
                win32gui.Rectangle(hdc, r[0], r[1], r[2], r[3])
                win32gui.SelectObject(hdc, old_pen)
                win32gui.SelectObject(hdc, old_brush)
                win32gui.DeleteObject(pen)
        finally:
            win32gui.ReleaseDC(hwnd, hdc)

    # ------------------------------------------------------------------ 窗口管理（仅渲染线程调用）

    def _ensure_window(self, vx, vy, vw, vh):
        if self._hwnd:
            if not win32gui.IsWindow(self._hwnd):
                self._hwnd = None  # 已被销毁：重建
            else:
                win32gui.SetWindowPos(
                    self._hwnd, win32con.HWND_TOPMOST, vx, vy, vw, vh,
                    win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                return
        hinst = win32api.GetModuleHandle(None)
        hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE,
            'STATIC',
            WINDOW_TITLE,
            win32con.WS_POPUP,
            vx, vy, vw, vh,
            None, None, hinst, None,
        )
        if not hwnd:
            logger.error('创建全局高亮窗口失败')
            return
        win32gui.SetLayeredWindowAttributes(hwnd, _COLORKEY, 255, win32con.LWA_COLORKEY)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        self._hwnd = hwnd
        logger.info('全局高亮窗口已创建 hwnd=%s 区域=(%s,%s,%s,%s)', hwnd, vx, vy, vw, vh)

    def _destroy_window(self):
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None
        self._last_key = None

    # ------------------------------------------------------------------ 渲染

    def render(self, frames: list):
        """绘制控件高亮框（纯边框，无标签/横幅）。
        :param frames: [{rect: [l,t,r,b] 屏幕物理坐标}]；空列表 = 清空高亮。
        frames 与上次一致时跳过重绘。
        ⚡ 同步语义：返回时渲染已完成（绘制实际在专用渲染线程执行，任意线程调用都安全）。
        """
        with self._cond:
            key = tuple(
                (f['rect'][0], f['rect'][1], f['rect'][2], f['rect'][3])
                for f in frames
            )
            if key == self._last_key:
                return  # 无变化：省资源
            self._last_key = key
            self._current_frames = [dict(f) for f in frames]
            self._schedule_render()


# 模块级单例（路由层使用）
highlight_service = HighlightService()
