# api/routers/ui_control_router.py
# 控件捕获工具接口（零悬浮窗、零层级切换、零轮询）：
#   GET/POST /api/ui-control/mode        捕获模式状态 / 进入退出
#   GET  /api/ui-control/events          SSE 事件流（选中/复制/模式状态 → 前端零轮询）
#   GET/PUT /api/settings/hotkeys        全局快捷键配置 + 冲突检测
import asyncio
import json
import threading
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.services import capture_mode


class ModeRequest(BaseModel):
    action: str                  # start | stop


class HotkeysRequest(BaseModel):
    hotkeys: dict                # {enter_capture/copy_generate/exit_mode: 'ctrl+shift+c'...}


def create_ui_control_router() -> APIRouter:
    capture_mode.ensure_hotkey_thread()
    router = APIRouter()

    # ---------------- 捕获模式 ----------------

    @router.get('/api/ui-control/mode')
    def mode_state():
        """捕获模式状态：active / 最近结果 / 全局热键注册状态"""
        return {'success': True, **capture_mode.get_state()}

    @router.post('/api/ui-control/mode')
    def mode_control(payload: ModeRequest):
        """进入/退出捕获模式（零模态：不拦截任何输入，鼠标悬停自动识别）"""
        if payload.action == 'start':
            result = capture_mode.start_mode()
            state = capture_mode.get_state()
            return {'ok': result.get('ok', True), 'message': result.get('message', ''), **state}
        elif payload.action == 'stop':
            capture_mode.stop_mode()
        return {'ok': True, **capture_mode.get_state()}

    # ---------------- SSE 事件流（前端零轮询：选中/复制/模式状态实时推送） ----------------

    @router.get('/api/ui-control/events')
    async def capture_events_sse():
        """SSE 长连接：捕获事件实时推送。前端不再轮询——
        悬停选中/生成节点/模式启停全部由后端主动推送（杜绝一切轮询访问）。"""
        q = capture_mode.subscribe_events()

        async def gen():
            try:
                while True:
                    item = await asyncio.to_thread(q.get)
                    yield f'data: {json.dumps(item, ensure_ascii=False)}\n\n'
            except asyncio.CancelledError:
                capture_mode.unsubscribe_events(q)
                raise
            except Exception:
                capture_mode.unsubscribe_events(q)
                raise

        return StreamingResponse(
            gen(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # ---------------- 快捷键配置（编辑菜单 → 快捷键设置） ----------------

    @router.get('/api/settings/hotkeys')
    def get_hotkeys():
        """读取全局快捷键配置 + 当前注册状态（冲突检测结果）"""
        return {
            'success': True,
            'hotkeys': capture_mode.load_hotkeys(),
            'registration': {
                'hotkey_ok': capture_mode.get_state()['hotkey_ok'],
                'message': capture_mode.get_state()['hotkey_msg'],
            },
        }

    @router.put('/api/settings/hotkeys')
    def put_hotkeys(payload: HotkeysRequest):
        """更新全局快捷键（带冲突检测）。enter_capture 立即重注册并校验占用；
        三个功能快捷键不允许相同。"""
        import time as _t

        hotkeys = payload.hotkeys or {}
        merged = capture_mode.save_hotkeys(hotkeys)
        # ⚡ H2：三个功能快捷键不允许相同
        values = [merged.get(k) for k in ('enter_capture', 'copy_generate', 'exit_mode')]
        if len(set(values)) != len(values):
            return {
                'ok': False,
                'message': '三个功能快捷键不能设置为相同组合，请重新选择',
                'hotkeys': merged,
                'registration': {'hotkey_ok': False, 'message': '快捷键重复'},
            }
        if 'enter_capture' in hotkeys and hotkeys['enter_capture']:
            capture_mode.apply_enter_hotkey(str(hotkeys['enter_capture']))
            # ⚡ 等待热键窗口线程完成重注册，且按 combo 匹配本次请求结果（防并发覆盖）
            deadline = _t.time() + 1.0
            apply_result = None
            while _t.time() < deadline:
                candidate = capture_mode.get_hotkey_apply_result()
                if candidate and candidate.get('combo') == str(hotkeys['enter_capture']):
                    apply_result = candidate
                    break
                _t.sleep(0.02)
            ok = bool(apply_result.get('ok')) if apply_result else False
            message = (apply_result or {}).get('message') or (capture_mode.get_state()['hotkey_msg'] or '快捷键已更新')
        else:
            ok = capture_mode.get_state()['hotkey_ok']
            message = capture_mode.get_state()['hotkey_msg'] or '快捷键已更新'
        return {
            'ok': ok,
            'message': message,
            'hotkeys': merged,
            'registration': {'hotkey_ok': ok, 'message': message},
        }

    return router
