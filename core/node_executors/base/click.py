# core/node_executors/base/click.py
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.services.input_dispatcher import click_workspace, physical_fallback_allowed
from core.services.input_verification import (
    capture_signature,
    mark_background_input_supported,
    mark_background_input_unsupported,
    verify_frame_change,
)


@NodeExecutorRegistry.register('click')
class ClickNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params

        pos = params.get('position', [0, 0])
        if isinstance(pos, list) and len(pos) >= 2:
            x, y = pos[0], pos[1]
        else:
            x, y = 0, 0

        button = str(params.get('button') or 'left')
        input_mode = str(params.get('input_mode') or 'background')
        verification_mode = str(params.get('verification_mode') or 'none').strip().lower()
        before = None
        if verification_mode == 'frame_change':
            try:
                before = capture_signature(context)
            except Exception as exc:
                return self.build_result(False, error=f'点击前置画面无法采集，不能执行后置验证: {exc}')
        result = click_workspace(
            context,
            x,
            y,
            reference_size=params.get('position_reference_size'),
            button=button,
            requested_mode=input_mode,
        )
        if result.get('ok') and before is not None:
            verification = verify_frame_change(
                context,
                before,
                timeout_ms=int(params.get('verification_timeout_ms') or 600),
                poll_ms=int(context.get_setting('match_poll_ms', 100)),
            )
            result['verification'] = verification
            if verification.get('verified'):
                if result.get('method') == 'background':
                    mark_background_input_supported(context)
                result['verified'] = True
                result['delivery'] = 'effect_verified'
                result['message'] = f'{result.get("message", "输入已投递")}；画面变化验证通过'
            elif result.get('method') == 'background':
                reason = (
                    f'后台消息已投递，但 {verification.get("elapsed_ms", 0):.0f}ms 内未检测到画面变化'
                )
                mark_background_input_unsupported(context, reason)
                if physical_fallback_allowed(context):
                    context.log(f'[输入验证] {reason}；按项目设置重试物理点击', 'warning')
                    physical = click_workspace(
                        context,
                        x,
                        y,
                        reference_size=params.get('position_reference_size'),
                        button=button,
                        requested_mode='physical',
                    )
                    physical['fallback_reason'] = reason
                    if physical.get('ok'):
                        physical_verification = verify_frame_change(
                            context,
                            before,
                            timeout_ms=int(params.get('verification_timeout_ms') or 600),
                            poll_ms=int(context.get_setting('match_poll_ms', 100)),
                        )
                        physical['verification'] = physical_verification
                        physical['verified'] = bool(physical_verification.get('verified'))
                        physical['delivery'] = 'effect_verified' if physical['verified'] else 'effect_unverified'
                        if not physical['verified']:
                            physical['ok'] = False
                            physical['message'] = '物理点击已执行，但画面变化后置验证仍未通过'
                    result = physical
                else:
                    result['ok'] = False
                    result['delivery'] = 'effect_unverified'
                    result['message'] = f'{reason}；项目未开启物理输入回退，已停止节点'
            else:
                result['ok'] = False
                result['delivery'] = 'effect_unverified'
                result['message'] = '输入已投递，但点击后画面变化验证未通过'
        success = bool(result.get('ok'))
        workspace_pos = result.get('workspace_point') or [x, y]
        transport = result.get('android_point') or result.get('screen_point') or []
        context.log(
            f' 点击[{result.get("method", "none")}] 工作区坐标({workspace_pos[0]}, {workspace_pos[1]})'
            + (f' -> 投递坐标{tuple(transport)}' if transport else '')
            + f' | {result.get("message", "")}',
            'info' if success else 'error',
        )

        return self.build_result(
            success,
            error=None if success else result.get('message'),
            extra={'input': result},
        )
