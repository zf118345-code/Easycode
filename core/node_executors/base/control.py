# core/node_executors/base/control.py
# 控件操作执行器：按选择器查找控件并执行操作（点击/双击/悬停）
import re

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.control_service import find_control, perform_action
from core.utils import resolve_template_string


@NodeExecutorRegistry.register('control')
class ControlNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        action = params.get('action', 'click')
        by = params.get('by', 'uia_name')
        target = resolve_template_string(params.get('target', ''), context).strip()
        window_title = resolve_template_string(params.get('window_title', ''), context).strip()
        try:
            index = int(params.get('index', 0) or 0)
        except (TypeError, ValueError):
            index = 0
        try:
            timeout_ms = int(params.get('timeout', 3000) or 3000)
        except (TypeError, ValueError):
            timeout_ms = 3000

        # ⚡ target 为捕获格式（name="x"/type="x"/id="x"/class="x"）时自动推断 UIA 查找方式
        by, target = self._infer_selector(by, target)

        # ⚡ 捕获时存储的完整控件信息（隐藏字段，表单不展示）：执行时用于
        # 1) 窗口作用域（避免全桌面 UIA 遍历，快速定位）；2) 主选择器未命中时的备选重查
        control_info = params.get('control_info') or {}
        if not isinstance(control_info, dict):
            control_info = {}
        if not window_title:
            wt = str(control_info.get('window_title') or '').strip()
            if wt:
                window_title = wt

        if not target:
            context.log('⚠️ [控件操作] 未配置控件名称（控件名称为空），已跳过', 'warning')
            return self.build_jump_result(True, params.get('on_success', {}))

        context.log(
            f'🎛️ [控件操作] 查找控件 | 方式: {by} | 标识: {target!r} | '
            f'窗口: {window_title or "全部"} | 序号: {index} | 超时: {timeout_ms}ms'
        )
        if by.startswith('uia_'):
            # ⚡ UIA 查找（浏览器/自绘控件，元素级）
            from core.services import uia_service

            info = None
            # 1) 祖先链优先：捕获时记录的路径（顶层窗口→控件）逐级下降定位，毫秒级且不错位
            path = (control_info or {}).get('ancestor_path')
            if isinstance(path, list) and path:
                info = uia_service.find_control_by_path(
                    window_title=window_title, path=path, timeout_ms=min(timeout_ms, 1500)
                )
            # 2) 位置锚点：固定位置控件（任务栏/桌面图标等树遍历不可靠的场景）rect 中心命中 + 身份校验
            if info is None:
                info = uia_service.find_control_by_rect(
                    (control_info or {}).get('rect'),
                    expect_name=(control_info or {}).get('name'),
                    expect_aid=(control_info or {}).get('automation_id'),
                    expect_type=(control_info or {}).get('control_type'),
                )
            # 3) 主选择器 BFS（旧节点无 path 或 path 失效时）
            if info is None:
                info = uia_service.find_control(
                    window_title=window_title, by=by, target=target, index=index, timeout_ms=timeout_ms
                )
            # 3) 主选择器未命中 → 用捕获信息里的其他字段（automation_id/class/name/type）依次兜底重查
            if info is None and control_info:
                info = _find_with_captured_fallbacks(
                    uia_service, window_title, by, target, index, timeout_ms, control_info
                )
            if info is not None:
                hit_note = ''
                if info.get('matched_by') == 'path':
                    hit_note = '（祖先链定位）'
                elif info.get('matched_by') == 'rect':
                    hit_note = '（位置锚点）'
                elif info.get('matched_by'):
                    hit_note = f'（备选 {info["matched_by"]}={info.get("matched_target", "")}）'
                context.log(
                    f'🎯 [控件操作] 命中 UIA 元素 | name={info.get("name", "")!r} | '
                    f'type={info.get("control_type", "")} | id={info.get("automation_id", "")} | '
                    f'坐标={info.get("rect", [])}{hit_note}'
                )
        else:
            info = find_control(
                window_title=window_title, by=by, target=target, index=index, timeout_ms=timeout_ms
            )

        if info is None:
            context.log(f'❌ [控件操作] 未找到匹配控件 [{target}]（超时 {timeout_ms}ms）')
            return self.build_jump_result(False, params.get('on_failure', {}))

        if not by.startswith('uia_'):
            context.log(
                f'🎯 [控件操作] 命中控件 | class={info.get("class_name", "")} | '
                f'text={info.get("text", "")!r} | 坐标={info.get("rect", [])}'
            )

        if by.startswith('uia_'):
            from core.services import uia_service

            result = uia_service.perform_uia_action(info, action)
        else:
            result = perform_action(info, action)

        if not result.get('ok'):
            context.log(f'❌ [控件操作] {result.get("message", "操作执行失败")}')
            return self.build_jump_result(False, params.get('on_failure', {}))

        context.log(f'✅ [控件操作] {result.get("message", "操作成功")}')
        return self.build_jump_result(True, params.get('on_success', {}))

    @staticmethod
    def _infer_selector(by, target):
        """捕获格式 name="x"/type="x"/id="x"/class="x" → 自动推断 UIA 查找方式；
        手动指定了 Win32 by 时保持原样。"""
        text = (target or '').strip()
        m = re.match(r'^(name|type|id|class)="([^"]*)"$', text)
        if m and not by.startswith('uia_'):
            kind, value = m.group(1), m.group(2).strip()
            mapping = {'name': 'uia_name', 'type': 'uia_type', 'id': 'uia_id', 'class': 'uia_class'}
            return mapping[kind], value
        return by, text


def _find_with_captured_fallbacks(uia_service, window_title, by, target, index, timeout_ms, control_info):
    """主选择器未命中时，按捕获信息里的其余字段（id/class/name/type）依次兜底重查。
    捕获时控件身份已确定（automation_id/class 比展示名更稳定），兜底顺序取最具体者优先；
    每个兜底用短超时（窗口作用域内查找很快），命中即返回并记录实际命中的方式。"""
    primary = (by, target)
    fallbacks = []
    for alt_by, key in (
        ('uia_id', 'automation_id'),
        ('uia_class', 'class_name'),
        ('uia_name', 'name'),
        ('uia_type', 'control_type'),
    ):
        value = str(control_info.get(key) or '').strip()
        if value and (alt_by, value) != primary:
            fallbacks.append((alt_by, value))
    fallback_timeout = min(int(timeout_ms or 3000), 1500)
    for alt_by, value in fallbacks:
        info = uia_service.find_control(
            window_title=window_title, by=alt_by, target=value, index=index, timeout_ms=fallback_timeout
        )
        if info is not None:
            info['matched_by'] = alt_by
            info['matched_target'] = value
            return info
    return None
