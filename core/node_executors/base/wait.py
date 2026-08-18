# core/node_executors/base/wait.py
import time

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('wait')
class WaitNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        duration_ms = params.get('duration_ms')
        if duration_ms is None and params.get('seconds') is not None:
            # 旧数据兼容：seconds 单位为秒 → 毫秒
            duration_ms = float(params['seconds']) * 1000
        duration_ms = float(duration_ms if duration_ms is not None else 1000)
        context.log(f'等待 {duration_ms:.0f} ms')
        time.sleep(duration_ms / 1000.0)

        # ⭐ 支持通过 on_success 灵活控制跳转
        return self.build_jump_result(True, params.get('on_success', {}))
